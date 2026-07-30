function cleanBusinessName(audit) {
  const raw = audit?.domain || audit?.normalized_url || 'this business'
  try {
    return new URL(audit?.normalized_url || `https://${raw}`).hostname
      .replace(/^www\./, '')
      .split('.')[0]
      .replace(/[-_]+/g, ' ')
      .replace(/\b\w/g, char => char.toUpperCase())
  } catch {
    return String(raw).replace(/^www\./, '').split('.')[0]
  }
}

export function buildAuditBuyerQuestions(audit) {
  const name = cleanBusinessName(audit)
  const suggestedQuestions = (audit?.content_suggestions || [])
    .map(item => item?.target_question?.trim())
    .filter(Boolean)

  const fallbacks = [
    `What does ${name} do and who is it best for?`,
    `Would you recommend ${name} for someone looking for its services?`,
    `What are the best alternatives to ${name}?`,
  ]

  return [...new Set([...suggestedQuestions, ...fallbacks])].slice(0, 3)
}
