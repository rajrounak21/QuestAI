/**
 * Turns a free-text question into the structured fields the job search form
 * uses. Lives outside JobSearch so both the "Try" chips and the dashboard
 * deep link (/jobs?q=...) can share one set of parsing rules.
 *
 * "AI Engineer Internships in India remote" -> role, ["India"], "remote"
 * Neither caller ever searches on its own — they only fill the form.
 */
export function parseQuery(s) {
  let rest = String(s || '').trim()
  let mode = ''

  for (const m of ['remote', 'hybrid', 'onsite', 'on-site']) {
    const re = new RegExp(`\\s*\\b${m}\\b\\s*$`, 'i')
    if (re.test(rest)) {
      mode = m === 'on-site' ? 'onsite' : m
      rest = rest.replace(re, '')
      break
    }
  }

  let rolePart = rest.trim()
  const locPart = []
  const m = rest.match(/^(.*?)\s+in\s+(.+)$/i)
  if (m) {
    rolePart = m[1].trim()
    locPart.push(...m[2].split(',').map((x) => x.trim()).filter(Boolean))
  }

  // Trim the plural "internships"/"jobs" off the role tail.
  rolePart = rolePart.replace(/\s+(internships?|jobs?)$/i, '').trim()

  return {
    role: rolePart,
    locations: locPart.slice(0, 4),
    mode,
  }
}
