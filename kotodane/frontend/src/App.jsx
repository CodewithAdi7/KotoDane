import { useState } from 'react'
import './App.css'

const API_BASE = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/+$/, '')

async function readResponse(response, action) {
  if (!response.ok) {
    let detail = ''
    try {
      const body = await response.json()
      detail = body.detail || ''
    } catch {
      // The response may not contain JSON; the status message is still useful.
    }
    throw new Error(detail || `${action} failed (${response.status})`)
  }
  return response.json()
}

function App() {
  const [text, setText] = useState('')
  const [tokens, setTokens] = useState(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState('')
  const [knownCount, setKnownCount] = useState(null)

  async function renderText(event) {
    event.preventDefault()
    if (!text.trim() || isLoading) return

    setIsLoading(true)
    setError('')
    setTokens(null)

    try {
      const knownResponse = await fetch(`${API_BASE}/known-kanji`)
      const knownData = await readResponse(knownResponse, 'Could not load your known kanji')
      const knownKanji = Array.isArray(knownData.known_kanji) ? knownData.known_kanji : []
      setKnownCount(knownKanji.length)

      const renderResponse = await fetch(`${API_BASE}/render`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, known_kanji: knownKanji }),
      })
      const renderData = await readResponse(renderResponse, 'Could not render this text')
      setTokens(Array.isArray(renderData.tokens) ? renderData.tokens : [])
    } catch (requestError) {
      if (requestError instanceof TypeError) {
        setError(`Kotodane could not reach the local backend at ${API_BASE}. Start the backend and try again.`)
      } else {
        setError(requestError.message || 'Something went wrong while rendering.')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const maskedCount = tokens?.filter((token) => token.masked).length ?? 0

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#reader" aria-label="Kotodane reader home">
          <span className="brand-mark" aria-hidden="true">言</span>
          <span className="brand-name">kotodane</span>
        </a>
        <span className="local-indicator"><span aria-hidden="true" /> Local reading space</span>
      </header>

      <main id="reader" className="reader-layout">
        <section className="intro" aria-labelledby="page-title">
          <p className="eyebrow">YOUR JAPANESE READING DESK</p>
          <h1 id="page-title">A little more readable,<br /><span>one word at a time.</span></h1>
          <p className="intro-copy">Paste a sentence or a passage. Words with kanji you haven’t learned yet will show their reading in hiragana.</p>
        </section>

        <form className="reader-card" onSubmit={renderText}>
          <div className="card-heading">
            <label htmlFor="japanese-text">Your text</label>
            <span className="input-hint">Japanese text</span>
          </div>
          <textarea
            id="japanese-text"
            className="text-input"
            lang="ja"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="ここに日本語を貼り付けてください。\n\nPaste Japanese text here…"
            rows={7}
            spellCheck="false"
            aria-describedby="input-note"
          />
          <div className="input-footer">
            <span id="input-note">Your text stays on this device.</span>
            <span>{text.length.toLocaleString()} characters</span>
          </div>
          <div className="action-row">
            <p className="known-note" aria-live="polite">
              {knownCount === 0
                ? 'No known kanji saved yet; kanji in the passage will be shown in hiragana.'
                : knownCount === null
                  ? 'Your known kanji will be kept as-is.'
                  : `${knownCount} known kanji will be kept as-is.`}
            </p>
            <button className="render-button" type="submit" disabled={isLoading || !text.trim()}>
              {isLoading ? (
                <><span className="spinner" aria-hidden="true" /> Rendering</>
              ) : (
                <>Render text <span aria-hidden="true">→</span></>
              )}
            </button>
          </div>
        </form>

        <section className="output-card" aria-labelledby="output-title" aria-live="polite">
          <div className="output-heading">
            <div>
              <p className="eyebrow">READING VIEW</p>
              <h2 id="output-title">Your passage</h2>
            </div>
            {tokens !== null && !error && (
              <span className="result-count">
                {maskedCount === 0 ? 'All kanji familiar' : `${maskedCount} ${maskedCount === 1 ? 'word' : 'words'} with readings`}
              </span>
            )}
          </div>

          {error ? (
            <div className="message message-error" role="alert">
              <span className="message-icon" aria-hidden="true">!</span>
              <div><strong>We couldn’t render that just now.</strong><p>{error}</p></div>
            </div>
          ) : tokens === null ? (
            <div className="empty-state">
              <span className="empty-symbol" aria-hidden="true">あ</span>
              <p>Your reading will appear here.</p>
              <span>Unknown kanji will have a gentle dotted underline.</span>
            </div>
          ) : (
            <div className="rendered-text" lang="ja">
              {tokens.map((token, index) => (
                <span
                  className={token.masked ? 'word-token is-masked' : 'word-token'}
                  key={`${index}-${token.surface}`}
                  title={token.masked ? `Reading: ${token.reading_hiragana}` : undefined}
                >
                  {token.display}
                </span>
              ))}
            </div>
          )}
        </section>

        <footer className="page-footer">
          <span>Take your time. 読むことを楽しもう。</span>
          <span className="footer-dot" aria-hidden="true">✳</span>
        </footer>
      </main>
    </div>
  )
}

export default App
