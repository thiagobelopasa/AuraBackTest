/**
 * Validação de licença do Aura Marketplace.
 *
 * Endpoint: GET https://api.auraplatforms.net/licenses/validate?key=KEY
 * Doc oficial: https://marketplace.auraplatforms.net (resposta JSON com valid/reason/expires_at).
 *
 * Estados retornados por getStatus():
 *   ACTIVE    — licença válida (online ou em grace offline)
 *   READONLY  — expirada / revogada / offline > grace. App permite Histórico mas bloqueia features
 *   BLOCKED   — nunca ativou (sem chave) ou chave de produto errado. Mostra tela de ativação
 *
 * Comportamento:
 *   - Cache local cifrado (AES-256-CBC) em userData/license.dat
 *   - Re-valida online a cada 24h
 *   - Tolerância offline: 30 dias após última validação bem-sucedida
 *   - Se EXPECTED_PRODUCT_ID estiver vazio, aceita qualquer chave válida.
 *     Atualize para o UUID do produto AuraBackTest assim que cadastrar no Marketplace.
 */
const { net } = require('electron')
const fs = require('fs')
const path = require('path')
const crypto = require('crypto')
const os = require('os')

const API_URL = 'https://api.auraplatforms.net/licenses/validate'

// TODO: preencher com o UUID do produto AuraBackTest no Marketplace Aura.
// Enquanto vazio, qualquer licença válida do marketplace é aceita (não recomendado em produção).
const EXPECTED_PRODUCT_ID = ''

const ONLINE_REVALIDATE_INTERVAL_MS = 24 * 60 * 60 * 1000  // 24h
const OFFLINE_GRACE_DAYS = 30
const REQUEST_TIMEOUT_MS = 8000

let cacheDir = null

function deriveKey() {
  // Derivação determinística: mesmo hostname + appId → mesma chave.
  // Não protege contra reverso, mas evita edição casual do cache.
  const seed = `${os.hostname()}|aurabacktest|com.aurabacktest.app`
  return crypto.scryptSync(seed, 'aurabacktest-license-v1', 32)
}

function encrypt(plain) {
  const iv = crypto.randomBytes(16)
  const cipher = crypto.createCipheriv('aes-256-cbc', deriveKey(), iv)
  const buf = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()])
  return Buffer.concat([iv, buf]).toString('base64')
}

function decrypt(payload) {
  try {
    const buf = Buffer.from(payload, 'base64')
    if (buf.length < 17) return null
    const iv = buf.subarray(0, 16)
    const data = buf.subarray(16)
    const decipher = crypto.createDecipheriv('aes-256-cbc', deriveKey(), iv)
    return Buffer.concat([decipher.update(data), decipher.final()]).toString('utf8')
  } catch {
    return null
  }
}

function cachePath() {
  return path.join(cacheDir, 'license.dat')
}

function readCache() {
  try {
    if (!cacheDir || !fs.existsSync(cachePath())) return null
    const enc = fs.readFileSync(cachePath(), 'utf8').trim()
    if (!enc) return null
    const json = decrypt(enc)
    if (!json) return null
    return JSON.parse(json)
  } catch {
    return null
  }
}

function writeCache(data) {
  try {
    if (!cacheDir) return
    if (!fs.existsSync(cacheDir)) fs.mkdirSync(cacheDir, { recursive: true })
    fs.writeFileSync(cachePath(), encrypt(JSON.stringify(data)), 'utf8')
  } catch (e) {
    // silencioso — runtime continua, só sem persistência
  }
}

function clearCache() {
  try {
    if (cacheDir && fs.existsSync(cachePath())) fs.unlinkSync(cachePath())
  } catch {}
}

function isExpired(expires_at) {
  if (!expires_at) return false  // null = vitalícia
  return new Date(expires_at).getTime() < Date.now()
}

function daysBetweenNow(iso) {
  if (!iso) return Infinity
  return (Date.now() - new Date(iso).getTime()) / (1000 * 60 * 60 * 24)
}

function validateOnline(key) {
  return new Promise((resolve) => {
    let finished = false
    const finish = (result) => {
      if (finished) return
      finished = true
      resolve(result)
    }

    const request = net.request({
      method: 'GET',
      url: `${API_URL}?key=${encodeURIComponent(key)}`,
    })
    request.setHeader('Accept', 'application/json')
    request.setHeader('User-Agent', 'AuraBackTest-Desktop')

    const timer = setTimeout(() => {
      try { request.abort() } catch {}
      finish({ ok: false, reason: 'timeout' })
    }, REQUEST_TIMEOUT_MS)

    request.on('response', (response) => {
      let body = ''
      response.on('data', (chunk) => { body += chunk.toString() })
      response.on('end', () => {
        clearTimeout(timer)
        if (response.statusCode === 429) {
          return finish({ ok: false, reason: 'rate_limited' })
        }
        try {
          const data = JSON.parse(body)
          finish({ ok: true, data, status: response.statusCode })
        } catch {
          finish({ ok: false, reason: 'parse_error' })
        }
      })
      response.on('error', () => {
        clearTimeout(timer)
        finish({ ok: false, reason: 'network_error' })
      })
    })
    request.on('error', () => {
      clearTimeout(timer)
      finish({ ok: false, reason: 'network_error' })
    })

    try {
      request.end()
    } catch {
      clearTimeout(timer)
      finish({ ok: false, reason: 'network_error' })
    }
  })
}

/**
 * Verifica estado da licença usando cache + revalidação online se necessário.
 * Retorna: { state: 'ACTIVE' | 'READONLY' | 'BLOCKED', reason?, info?, offline? }
 */
async function getStatus() {
  const cache = readCache()
  if (!cache || !cache.key) {
    return { state: 'BLOCKED', reason: 'no_key' }
  }

  const needsOnline = !cache.last_online_validation_at ||
    (Date.now() - new Date(cache.last_online_validation_at).getTime()) > ONLINE_REVALIDATE_INTERVAL_MS

  if (needsOnline) {
    const result = await validateOnline(cache.key)
    if (result.ok) {
      const data = result.data
      const nowIso = new Date().toISOString()
      if (!data.valid) {
        const updated = {
          ...cache,
          last_validated_at: nowIso,
          last_online_validation_at: nowIso,
          last_state: data.reason || 'invalid',
          last_reason: data.reason,
        }
        writeCache(updated)
        return { state: 'READONLY', reason: data.reason || 'invalid', info: updated }
      }

      // Validação adicional: product_id deve bater (se configurado)
      if (EXPECTED_PRODUCT_ID && data.product_id !== EXPECTED_PRODUCT_ID) {
        return { state: 'BLOCKED', reason: 'wrong_product' }
      }

      const updated = {
        ...cache,
        product_id: data.product_id,
        product_title: data.product_title,
        expires_at: data.expires_at,
        created_at: data.created_at || cache.created_at,
        last_validated_at: nowIso,
        last_online_validation_at: nowIso,
        last_state: 'valid',
      }
      writeCache(updated)

      if (isExpired(data.expires_at)) {
        return { state: 'READONLY', reason: 'expired', info: updated }
      }
      return { state: 'ACTIVE', info: updated }
    }

    // Falha de rede — recorre ao cache se estiver dentro do grace
    const daysOffline = daysBetweenNow(cache.last_online_validation_at)
    if (cache.last_state === 'valid' && !isExpired(cache.expires_at) && daysOffline <= OFFLINE_GRACE_DAYS) {
      return { state: 'ACTIVE', info: cache, offline: true, daysOffline: Math.floor(daysOffline) }
    }
    return { state: 'READONLY', reason: 'offline_grace_expired', info: cache, offline: true }
  }

  // Cache fresh — usa direto
  if (cache.last_state !== 'valid') {
    return { state: 'READONLY', reason: cache.last_state || 'invalid', info: cache }
  }
  if (isExpired(cache.expires_at)) {
    return { state: 'READONLY', reason: 'expired', info: cache }
  }
  return { state: 'ACTIVE', info: cache }
}

/**
 * Ativa uma licença. Valida online e, se OK, salva no cache.
 * Retorna: { ok: bool, reason?, info? }
 */
async function activate(key) {
  const trimmed = (key || '').trim()
  if (!trimmed) return { ok: false, reason: 'empty_key' }

  const result = await validateOnline(trimmed)
  if (!result.ok) return { ok: false, reason: result.reason || 'network_error' }
  const data = result.data
  if (!data.valid) return { ok: false, reason: data.reason || 'invalid' }
  if (EXPECTED_PRODUCT_ID && data.product_id !== EXPECTED_PRODUCT_ID) {
    return { ok: false, reason: 'wrong_product' }
  }

  const nowIso = new Date().toISOString()
  const cache = {
    key: trimmed,
    product_id: data.product_id,
    product_title: data.product_title,
    expires_at: data.expires_at,
    created_at: data.created_at,
    last_validated_at: nowIso,
    last_online_validation_at: nowIso,
    last_state: 'valid',
  }
  writeCache(cache)
  return { ok: true, info: cache }
}

function deactivate() {
  clearCache()
}

function getCachedInfo() {
  const c = readCache()
  if (!c) return null
  // Não expõe a chave completa pro renderer
  const masked = c.key ? `${c.key.slice(0, 8)}…${c.key.slice(-4)}` : null
  return {
    keyMasked: masked,
    product_id: c.product_id,
    product_title: c.product_title,
    expires_at: c.expires_at,
    created_at: c.created_at,
    last_validated_at: c.last_validated_at,
    last_state: c.last_state,
  }
}

function initialize(userDataPath) {
  cacheDir = userDataPath
}

module.exports = {
  initialize,
  getStatus,
  activate,
  deactivate,
  getCachedInfo,
  EXPECTED_PRODUCT_ID,
}
