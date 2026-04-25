import { useState } from 'react'
import './ContextualTooltip.css'

export function ContextualTooltip({ text, position = 'bottom', children }) {
  const [isVisible, setIsVisible] = useState(false)

  return (
    <div className="contextual-tooltip-wrapper">
      <div
        onMouseEnter={() => setIsVisible(true)}
        onMouseLeave={() => setIsVisible(false)}
      >
        {children}
      </div>
      {isVisible && (
        <div className={`contextual-tooltip contextual-tooltip-${position}`}>
          {text}
        </div>
      )}
    </div>
  )
}
