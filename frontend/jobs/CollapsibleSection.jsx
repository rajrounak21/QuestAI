import { useCallback, useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'

const KEY = (id) => `questai.jobs.section.${id}`

/**
 * Collapsible panel used for every section of the /jobs page.
 *
 * Two modes:
 *   uncontrolled (default) — owns its own open state and remembers it in
 *     localStorage, so a reload does not re-expand what the user folded away.
 *   controlled — pass `open` + `onOpen`, and the parent owns the state. The
 *     search form uses this so it can fold itself after a search returns.
 *
 * While collapsed the header keeps showing `summary`, so a closed section still
 * says what is inside it.
 *
 * The body stays mounted when closed (hidden, not unmounted) on purpose: the
 * search form and the filter groups both hold state in their own components, so
 * unmounting would throw away what the user had typed or ticked.
 */
export default function CollapsibleSection({
  id,
  icon: Icon,
  title,
  summary,
  defaultOpen = true,
  collapsible = true,
  open: openProp,
  onOpen,
  className = '',
  children,
}) {
  const controlled = openProp !== undefined

  const [internal, setInternal] = useState(() => {
    const stored = localStorage.getItem(KEY(id))
    if (stored === 'open') return true
    if (stored === 'closed') return false
    return defaultOpen
  })

  const open = controlled ? openProp : internal

  // Only the uncontrolled sections persist; a controlled one is the parent's
  // business and it already decides when to move it.
  useEffect(() => {
    if (!controlled) localStorage.setItem(KEY(id), open ? 'open' : 'closed')
  }, [id, open, controlled])

  const toggle = useCallback(() => {
    const next = !open
    if (!controlled) setInternal(next)
    onOpen && onOpen(next)
  }, [open, controlled, onOpen])

  const headMain = (
    <span className="csec-head-main">
      {Icon ? <Icon size={15} className="csec-icon" /> : null}
      <span className="csec-title">{title}</span>
    </span>
  )

  return (
    <section className={`csec${open ? ' is-open' : ''}${className ? ` ${className}` : ''}`}>
      {collapsible ? (
        <button
          type="button"
          className="csec-head"
          onClick={toggle}
          aria-expanded={open}
          aria-controls={`csec-body-${id}`}
        >
          {headMain}
          <span className="csec-head-right">
            {!open && summary ? <span className="csec-summary">{summary}</span> : null}
            <ChevronDown size={16} className="csec-chev" />
          </span>
        </button>
      ) : (
        <div className="csec-head is-static">
          {headMain}
          {summary ? <span className="csec-summary">{summary}</span> : null}
        </div>
      )}

      <div className="csec-body" id={`csec-body-${id}`} hidden={!open}>
        {children}
      </div>
    </section>
  )
}
