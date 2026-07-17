/**
 * Safe Markdown / HTML rendering for persisted content.
 *
 * Pipeline: Markdown → marked.parse → DOMPurify.sanitize → trusted HTML.
 * Never bind raw marked output (or mammoth HTML) to v-html without this step:
 * knowledge docs and attachment previews are stored content and must not
 * become a stored-XSS vector if a publisher account is compromised.
 *
 * Search / RAG excerpts stay plain text and must not use this helper.
 */

import DOMPurify, { type Config } from 'dompurify'
import { marked } from 'marked'

const PURIFY_CONFIG: Config = {
  USE_PROFILES: { html: true },
  // Keep target so we can force noopener on links in the hook below.
  ADD_ATTR: ['target'],
  FORBID_TAGS: ['style', 'form', 'input', 'button', 'textarea', 'select'],
  FORBID_ATTR: ['style'],
  RETURN_TRUSTED_TYPE: false,
}

let hooksInstalled = false

function ensureHooks(): void {
  if (hooksInstalled) {
    return
  }
  hooksInstalled = true
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (!(node instanceof Element)) {
      return
    }
    if (node.tagName === 'A') {
      const href = node.getAttribute('href') ?? ''
      if (/^\s*javascript:/i.test(href) || /^\s*data:/i.test(href) || /^\s*vbscript:/i.test(href)) {
        node.removeAttribute('href')
      }
      node.setAttribute('rel', 'noopener noreferrer')
      node.setAttribute('target', '_blank')
    }
    // Block javascript: / data: on media that can navigate.
    for (const attr of ['href', 'src', 'xlink:href']) {
      const value = node.getAttribute(attr)
      if (value && /^\s*(javascript|data|vbscript):/i.test(value)) {
        node.removeAttribute(attr)
      }
    }
  })
}

/** Sanitize already-produced HTML (mammoth, etc.). */
export function sanitizeHtml(html: string): string {
  ensureHooks()
  return String(DOMPurify.sanitize(html, PURIFY_CONFIG))
}

/** Parse Markdown then sanitize. Synchronous to keep callers simple. */
export function renderSafeMarkdown(source: string): string {
  const raw = marked.parse(source, { async: false })
  return sanitizeHtml(typeof raw === 'string' ? raw : String(raw))
}
