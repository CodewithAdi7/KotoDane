import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactCrop from "react-image-crop";
import "react-image-crop/dist/ReactCrop.css";
import "./App.css";

const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");
const kanjiChar = /^\p{Script=Han}$/u;

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body && !(options.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Could not reach the backend. Start the FastAPI server and try again.");
  }
  if (!response.ok) {
    const raw = await response.text();
    let detail = raw;
    try {
      detail = JSON.parse(raw).detail || raw;
    } catch {
      // Keep a plain-text backend error as-is.
    }
    if (response.status === 503 && String(detail).startsWith("Cannot connect to Ollama")) {
      detail = "Ollama is not running. Open Ollama, then choose Retry.";
    }
    throw new Error(detail || `The backend returned ${response.status}.`);
  }
  return response.json();
}

function normalizeKanji(payload) {
  return payload.known_kanji || payload.kanji || [];
}

function sentenceForToken(tokens, tokenIndex, text) {
  const start = tokens.slice(0, tokenIndex).reduce((offset, token) => offset + token.surface.length, 0);
  const boundaries = ["。", "！", "？", "!", "?", "\n", "\r"];
  const previousBoundary = Math.max(...boundaries.map((mark) => text.lastIndexOf(mark, Math.max(0, start - 1))));
  const sentenceStart = previousBoundary + 1;
  const rest = text.slice(start);
  const nextBoundary = rest.search(/[。！？!?\r\n]/u);
  const sentenceEnd = nextBoundary < 0 ? text.length : start + nextBoundary + 1;
  return text.slice(sentenceStart, sentenceEnd).trim();
}

function TokenRun({ tokens, onTokenClick, lexicalPos }) {
  return tokens.map((token, index) => lexicalPos(token.pos) ? (
    <button key={`${index}-${token.surface}`} className={`word-token word-button${token.masked ? " is-masked" : ""}`} onClick={() => onTokenClick(token, index, tokens)} title={`Look up ${token.surface}`} aria-label={`Look up ${token.surface}`}>
      {token.display}
    </button>
  ) : (
    <span key={`${index}-${token.surface}`} className={`word-token${token.masked ? " is-masked" : ""}`}>{token.display}</span>
  ));
}

function App() {
  const [page, setPage] = useState("reader");
  const [text, setText] = useState("");
  const [tokens, setTokens] = useState([]);
  const [knownKanji, setKnownKanji] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState("");
  const [managerError, setManagerError] = useState("");
  const [selected, setSelected] = useState(null);
  const [selectedSentence, setSelectedSentence] = useState("");
  const [lookup, setLookup] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [showOriginal, setShowOriginal] = useState(false);
  const [newKanji, setNewKanji] = useState("");
  const [saveState, setSaveState] = useState(null);
  const [cards, setCards] = useState([]);
  const [cardsLoading, setCardsLoading] = useState(false);
  const [cardsError, setCardsError] = useState("");
  const [activeImagePath, setActiveImagePath] = useState(null);

  const refreshKanji = useCallback(async () => {
    const result = await request("/known-kanji");
    const list = normalizeKanji(result);
    setKnownKanji(list);
    setCatalog((current) => [...new Set([...current, ...list])]);
    return list;
  }, []);

  useEffect(() => {
    setLoading(true);
    refreshKanji().catch((reason) => setManagerError(reason.message)).finally(() => setLoading(false));
  }, [refreshKanji]);

  const loadCards = useCallback(async () => {
    setCardsLoading(true);
    setCardsError("");
    try {
      const result = await request("/cards");
      setCards(result.cards || []);
    } catch (reason) {
      setCardsError(reason.message);
    } finally {
      setCardsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (page === "cards") loadCards();
  }, [page, loadCards]);

  const renderWith = useCallback(async (kanji) => {
    if (!text.trim()) {
      setTokens([]);
      return;
    }
    setRendering(true);
    setError("");
    try {
      const result = await request("/render", {
        method: "POST",
        body: JSON.stringify({ text, known_kanji: kanji }),
      });
      setTokens(result.tokens || []);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setRendering(false);
    }
  }, [text]);

  async function handleRender() {
    setError("");
    setRendering(true);
    try {
      const kanji = await refreshKanji();
      if (!text.trim()) {
        setTokens([]);
        setError("Paste or type Japanese text before rendering.");
        return;
      }
      const result = await request("/render", {
        method: "POST",
        body: JSON.stringify({ text, known_kanji: kanji }),
      });
      setTokens(result.tokens || []);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setRendering(false);
    }
  }

  async function processPanelText(panelText, imagePath) {
    setError("");
    setRendering(true);
    try {
      const kanji = await refreshKanji();
      const result = await request("/render", {
        method: "POST",
        body: JSON.stringify({ text: panelText, known_kanji: kanji }),
      });
      setText(panelText);
      setTokens(result.tokens || []);
      setActiveImagePath(imagePath);
      setPage("reader");
    } catch (reason) {
      setError(reason.message);
      throw reason;
    } finally {
      setRendering(false);
    }
  }

  async function openLookup(token, tokenIndex, sourceTokens = tokens, sourceText = text) {
    const word = token.lemma || token.surface;
    const sentence = sentenceForToken(sourceTokens, tokenIndex, sourceText) || token.surface;
    setSelected(token);
    setSelectedSentence(sentence);
    setLookup(null);
    setLookupError("");
    setSaveState({ status: "saving" });
    setShowOriginal(false);
    setLookupLoading(true);
    try {
      const data = await request(`/lookup?word=${encodeURIComponent(word)}`);
      setLookup(data);
      const firstSense = data.entries?.[0]?.senses?.[0];
      const meaning = firstSense?.glosses?.[0] || "";
      try {
        const result = await request("/cards", {
          method: "POST",
          body: JSON.stringify({
            lemma: word,
            reading: token.reading_hiragana || word,
            meaning,
            sentence,
            image_path: page === "reader" ? activeImagePath : null,
          }),
        });
        setSaveState({ status: "saved", created: result.created, card: result.card });
        setCards((current) => [result.card, ...current.filter((card) => card.lemma !== result.card.lemma)]);
      } catch (reason) {
        setSaveState({ status: "error", message: reason.message });
      }
    } catch (reason) {
      setLookupError(reason.message);
      setSaveState({ status: "error", message: reason.message });
    } finally {
      setLookupLoading(false);
    }
  }

  async function savePracticeExample(lemma, note) {
    const result = await request(`/cards/${encodeURIComponent(lemma)}/notes`, {
      method: "POST",
      body: JSON.stringify({ note }),
    });
    setCards((current) => [result.card, ...current.filter((card) => card.lemma !== result.card.lemma)]);
  }

  async function saveKanjiChange(add, remove) {
    setManagerError("");
    try {
      const result = await request("/known-kanji", {
        method: "PUT",
        body: JSON.stringify({ add, remove }),
      });
      const list = normalizeKanji(result);
      setKnownKanji(list);
      setCatalog((current) => [...new Set([...current, ...add, ...remove])]);
      if (selected) {
        setSelected(null);
        setLookup(null);
      }
      await renderWith(list);
    } catch (reason) {
      setManagerError(reason.message);
    }
  }

  async function seedKanji() {
    setManagerError("");
    setLoading(true);
    try {
      await request("/known-kanji/seed", { method: "POST" });
      const list = await refreshKanji();
      await renderWith(list);
    } catch (reason) {
      setManagerError(reason.message);
    } finally {
      setLoading(false);
    }
  }

  async function addKanji(event) {
    event.preventDefault();
    const character = newKanji.trim();
    if (!kanjiChar.test(character)) {
      setManagerError("Enter one kanji character.");
      return;
    }
    await saveKanjiChange([character], []);
    setCatalog((current) => [...new Set([...current, character])]);
    setNewKanji("");
  }

  const knownSet = useMemo(() => new Set(knownKanji), [knownKanji]);
  const sortedCatalog = useMemo(() => [...catalog].sort((a, b) => a.localeCompare(b, "ja")), [catalog]);
  const lexicalPos = (pos) => !["空白", "補助記号", "記号", "補助記号-句点", "補助記号-読点"].includes(pos);

  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="brand" href="#reader" onClick={() => setPage("reader")} aria-label="Kotodane home">
          <span className="brand-mark">言</span><span className="brand-name">kotodane</span>
        </a>
        <nav className="tabs" aria-label="Main navigation">
          <button className={page === "reader" ? "tab is-active" : "tab"} onClick={() => setPage("reader")}>Reader</button>
          <button className={page === "panel" ? "tab is-active" : "tab"} onClick={() => setPage("panel")}>Panel</button>
          <button className={page === "listen" ? "tab is-active" : "tab"} onClick={() => setPage("listen")}>Listen</button>
          <button className={page === "kanji" ? "tab is-active" : "tab"} onClick={() => setPage("kanji")}>Kanji</button>
          <button className={page === "cards" ? "tab is-active" : "tab"} onClick={() => setPage("cards")}>Cards</button>
        </nav>
        <div className="local-indicator"><span />Runs locally</div>
      </header>

      {page === "reader" ? (
        <main className="reader-layout">
          <section className="intro">
            <p className="eyebrow">READ AT YOUR OWN PACE</p>
            <h1>Make Japanese <span>readable.</span></h1>
            <p className="intro-copy">Paste a passage, reveal readings for kanji you haven’t learned yet, and tap a word whenever you want to look it up.</p>
          </section>
          <section className="reader-card">
            <div className="card-heading"><label htmlFor="japanese-text">Your Japanese text</label><span className="input-hint">A sentence, paragraph, or page</span></div>
            <textarea id="japanese-text" className="text-input" value={text} onChange={(event) => { setText(event.target.value); setActiveImagePath(null); }} placeholder="ここに日本語の文章を貼り付けてください。" spellCheck="false" />
            <div className="input-footer"><span>Japanese text stays on this device</span><span>{text.length} characters</span></div>
            <div className="action-row"><p className="known-note">{loading ? "Loading your kanji…" : `${knownKanji.length} kanji marked as known`}. Change these in the Kanji tab.</p><button className="render-button" onClick={handleRender} disabled={rendering || loading}>{rendering ? <><span className="spinner" />Rendering</> : "Render text"}</button></div>
          </section>
          {error && <ErrorMessage message={error} />}
          <section className="output-card">
            <div className="output-heading"><div><p className="eyebrow">YOUR READING VIEW</p><h2>Tap a word to explore it</h2></div>{tokens.length > 0 && <span className="result-count">{tokens.length} tokens</span>}</div>
            {tokens.length === 0 ? <div className="empty-state"><span className="empty-symbol">読</span><p>Your reading will appear here</p><span>Kanji outside your known list will show their hiragana reading.</span></div> : <div className="rendered-text" lang="ja"><TokenRun tokens={tokens} lexicalPos={lexicalPos} onTokenClick={(token, index) => openLookup(token, index)} /></div>}
          </section>
          {selected && <LookupPanel token={selected} sentence={selectedSentence} data={lookup} loading={lookupLoading} error={lookupError} saveState={saveState} showOriginal={showOriginal} onShowOriginal={setShowOriginal} onClose={() => { setSelected(null); setLookup(null); setSaveState(null); }} knownKanji={knownKanji} savedWords={cards.map((card) => card.lemma)} lexicalPos={lexicalPos} onWordClick={(token, index, sourceTokens) => openLookup(token, index, sourceTokens, sourceTokens.map((part) => part.surface).join(""))} onSaveExample={savePracticeExample} />}
          <footer className="page-footer"><span>Built for slow, curious reading.</span><span className="footer-dot">·</span><span>One word at a time</span></footer>
        </main>
      ) : page === "kanji" ? (
        <main className="manager-layout">
          <section className="intro"><p className="eyebrow">YOUR PERSONAL STUDY LIST</p><h1>Kanji you <span>know.</span></h1><p className="intro-copy">Mark familiar characters as known. Your reader updates the current passage as soon as the list changes.</p></section>
          <section className="manager-card">
            <div className="manager-heading"><div><p className="eyebrow">KANJI LIST</p><h2>{knownKanji.length} known</h2></div><button className="secondary-button" onClick={seedKanji} disabled={loading}>Seed starter list</button></div>
            <form className="add-kanji-form" onSubmit={addKanji}><label className="sr-only" htmlFor="new-kanji">Add a kanji</label><input id="new-kanji" value={newKanji} onChange={(event) => setNewKanji(event.target.value)} maxLength={2} placeholder="Add a kanji, e.g. 語" /><button className="render-button" type="submit">Add kanji</button></form>
            {managerError && <ErrorMessage message={managerError} />}
            {sortedCatalog.length === 0 ? <div className="manager-empty"><span className="empty-symbol">漢</span><p>No kanji in your list yet.</p><span>Add a character or seed the starter list.</span></div> : <div className="kanji-grid">{sortedCatalog.map((character) => { const isKnown = knownSet.has(character); return <button key={character} className={`kanji-tile${isKnown ? " is-known" : ""}`} onClick={() => saveKanjiChange(isKnown ? [] : [character], isKnown ? [character] : [])} aria-pressed={isKnown}><span className="kanji-character">{character}</span><span className="kanji-status">{isKnown ? "Known" : "Not known"}</span></button>; })}</div>}
          </section>
          <footer className="page-footer"><span>Changes are saved on this device.</span><span className="footer-dot">·</span><button className="text-button" onClick={() => setPage("reader")}>Back to reader</button></footer>
        </main>
      ) : page === "cards" ? (
        <main className="cards-layout">
          <section className="intro"><p className="eyebrow">YOUR SAVED VOCABULARY</p><h1>Words to <span>keep.</span></h1><p className="intro-copy">Words you look up are saved here with their reading, meaning, and the sentence they came from.</p></section>
          <section className="cards-card">
            <div className="manager-heading"><div><p className="eyebrow">VOCABULARY CARDS</p><h2>{cards.length} saved {cards.length === 1 ? "word" : "words"}</h2></div><button className="secondary-button" onClick={loadCards} disabled={cardsLoading}>Refresh</button></div>
            {cardsError && <ErrorMessage message={cardsError} />}
            {cardsLoading && cards.length === 0 ? <p className="lookup-status">Loading saved cards…</p> : cards.length === 0 ? <div className="manager-empty"><span className="empty-symbol">語</span><p>No saved words yet.</p><span>Tap a word in Reader to save it here.</span></div> : <div className="saved-card-list">{cards.map((card) => <article className="saved-card" key={card.id}>{card.image_path && <img className="card-thumbnail" src={`${API_URL}${card.image_path}`} alt={`Cropped manga panel for ${card.lemma}`} loading="lazy" />}<div className="saved-card-heading"><div><h3 lang="ja">{card.lemma}</h3><span lang="ja">{card.reading}</span></div><span className="tap-count">Tapped {card.tap_count} {card.tap_count === 1 ? "time" : "times"}</span></div><p className="saved-meaning">{card.meaning || "Meaning not found in the local dictionary."}</p><p className="saved-sentence" lang="ja">{card.sentence}</p>{card.notes && <div className="card-examples"><p className="eyebrow">PRACTICE EXAMPLES</p>{card.notes.split("\n").map((note, index) => <p className="saved-example" lang="ja" key={`${index}-${note}`}>{note}</p>)}</div>}</article>)}</div>}
          </section>
          <footer className="page-footer"><span>Saved on this device.</span><span className="footer-dot">·</span><button className="text-button" onClick={() => setPage("reader")}>Back to reader</button></footer>
        </main>
      ) : page === "listen" ? (
        <>
          <ListenPage
            knownKanji={knownKanji}
            lexicalPos={lexicalPos}
            onWordClick={(token, index, sourceTokens) => openLookup(
              token,
              index,
              sourceTokens,
              sourceTokens.map((part) => part.surface).join(""),
            )}
          />
          {selected && <div className="listen-lookup"><LookupPanel token={selected} sentence={selectedSentence} data={lookup} loading={lookupLoading} error={lookupError} saveState={saveState} showOriginal={showOriginal} onShowOriginal={setShowOriginal} onClose={() => { setSelected(null); setLookup(null); setSaveState(null); }} knownKanji={knownKanji} savedWords={cards.map((card) => card.lemma)} lexicalPos={lexicalPos} onWordClick={(token, index, sourceTokens) => openLookup(token, index, sourceTokens, sourceTokens.map((part) => part.surface).join(""))} onSaveExample={savePracticeExample} /></div>}
        </>
      ) : (
        <PanelPage onProcessText={processPanelText} />
      )}
    </div>
  );
}

function ListenPage({ knownKanji, lexicalPos, onWordClick }) {
  const [file, setFile] = useState(null);
  const [segments, setSegments] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(event) {
    event.preventDefault();
    if (!file) {
      setError("Choose an audio or video clip first.");
      return;
    }
    setBusy(true);
    setError("");
    setSegments([]);
    const form = new FormData();
    form.append("file", file);
    try {
      const result = await request("/transcribe", { method: "POST", body: form });
      setSegments(result.segments || []);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  return <main className="listen-layout">
    <section className="intro"><p className="eyebrow">JAPANESE LISTENING PRACTICE</p><h1>Listen. <span>Then read.</span></h1><p className="intro-copy">Upload a short clip to get a Japanese transcript, kanji readings, and a word familiarity estimate.</p></section>
    <section className="listen-card">
      <form onSubmit={submit}>
        <div className="manager-heading"><div><p className="eyebrow">AUDIO INPUT</p><h2>Choose a clip</h2></div><label className="secondary-button upload-control">{file ? "Choose another clip" : "Upload audio or video"}<input type="file" accept="audio/*,video/*,.m4a,.mkv,.mov,.mp4,.webm" onChange={(event) => { setFile(event.target.files?.[0] || null); setSegments([]); setError(""); }} /></label></div>
        <div className="listen-upload-details">{file ? <span>{file.name} · {(file.size / (1024 * 1024)).toFixed(1)} MB</span> : <span>Audio or video, up to 60 seconds and 50 MB</span>}<span>{knownKanji.length} kanji known · saved cards count as known words</span></div>
        <div className="panel-process-row"><p className="panel-note">Processing stays on this computer. First use downloads the Whisper model.</p><button className="render-button" type="submit" disabled={!file || busy}>{busy ? <><span className="spinner" />Transcribing</> : "Transcribe clip"}</button></div>
      </form>
      {busy && <p className="tutor-loading" role="status"><span className="spinner tutor-spinner" />Transcribing locally. The first run may take longer while the model downloads.</p>}
      {error && <ErrorMessage message={error} />}
      {segments.length > 0 ? <div className="transcript-list">{segments.map((segment, index) => <article className="transcript-segment" key={`${segment.start}-${index}`}>
        <div className="transcript-heading"><p className="eyebrow">SEGMENT {index + 1} · {Number(segment.start).toFixed(1)}–{Number(segment.end).toFixed(1)}s</p><span className="known-percent">{segment.known_words_percent}% words known</span></div>
        <div className="rendered-text transcript-text" lang="ja"><TokenRun tokens={segment.tokens} lexicalPos={lexicalPos} onTokenClick={(token, tokenIndex, sourceTokens) => onWordClick(token, tokenIndex, sourceTokens)} /></div>
        <p className="transcript-original" lang="ja">{segment.text}</p>
      </article>)}</div> : !busy && !error && <div className="panel-empty"><span className="empty-symbol">聴</span><p>Your transcript will appear here.</p><span>Tap an underlined word to open its dictionary and tutor panel.</span></div>}
    </section>
    <footer className="page-footer"><span>Japanese model: Whisper small.</span><span className="footer-dot">·</span><span>Transcript remains local.</span></footer>
  </main>;
}

function ErrorMessage({ message }) {
  return <div className="message message-error" role="alert"><span className="message-icon">!</span><div><strong>Something needs attention</strong><p>{message}</p></div></div>;
}

async function makeCropBlob(image, crop) {
  if (!image || !crop?.width || !crop?.height) throw new Error("Drag a crop box around one speech bubble first.");
  const scaleX = image.naturalWidth / image.width;
  const scaleY = image.naturalHeight / image.height;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(crop.width * scaleX));
  canvas.height = Math.max(1, Math.round(crop.height * scaleY));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("This browser could not create the cropped image.");
  context.drawImage(
    image,
    crop.x * scaleX,
    crop.y * scaleY,
    crop.width * scaleX,
    crop.height * scaleY,
    0,
    0,
    canvas.width,
    canvas.height,
  );
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error("Could not create the cropped image.")), "image/png");
  });
}

function PanelPage({ onProcessText }) {
  const imageRef = useRef(null);
  const [sourceFile, setSourceFile] = useState(null);
  const [sourceUrl, setSourceUrl] = useState("");
  const [crop, setCrop] = useState();
  const [completedCrop, setCompletedCrop] = useState(null);
  const [cropBlob, setCropBlob] = useState(null);
  const [ocrText, setOcrText] = useState("");
  const [reading, setReading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!sourceFile) {
      setSourceUrl("");
      return undefined;
    }
    const url = URL.createObjectURL(sourceFile);
    setSourceUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [sourceFile]);

  function chooseImage(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Choose a JPEG, PNG, or WebP image.");
      event.target.value = "";
      return;
    }
    setSourceFile(file);
    event.target.value = "";
    setCrop(undefined);
    setCompletedCrop(null);
    setCropBlob(null);
    setOcrText("");
    setError("");
  }

  async function readBubble() {
    setError("");
    setReading(true);
    try {
      const blob = await makeCropBlob(imageRef.current, completedCrop);
      setCropBlob(blob);
      const form = new FormData();
      form.append("file", blob, "speech-bubble.png");
      const result = await request("/ocr", { method: "POST", body: form });
      setOcrText(result.text || "");
      if (!result.text?.trim()) setError("No text was recognized. Try a tighter crop around the bubble.");
    } catch (reason) {
      setError(reason.message);
    } finally {
      setReading(false);
    }
  }

  async function processText() {
    setError("");
    if (!ocrText.trim()) {
      setError("Read a bubble and check its text before processing.");
      return;
    }
    setProcessing(true);
    try {
      const blob = cropBlob || await makeCropBlob(imageRef.current, completedCrop);
      const form = new FormData();
      form.append("file", blob, "speech-bubble.png");
      const saved = await request("/images", { method: "POST", body: form });
      await onProcessText(ocrText, saved.image_path);
    } catch (reason) {
      setError(reason.message);
    } finally {
      setProcessing(false);
    }
  }

  return <main className="panel-layout">
    <section className="intro"><p className="eyebrow">READ FROM A MANGA PANEL</p><h1>Crop a bubble. <span>Read it.</span></h1><p className="intro-copy">Choose a page image, drag a box around one speech bubble, and let the local OCR read it.</p></section>
    <section className="panel-card">
      <div className="manager-heading"><div><p className="eyebrow">IMAGE INPUT</p><h2>Choose a page</h2></div><label className="secondary-button upload-control">{sourceFile ? "Choose another image" : "Upload image"}<input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseImage} /></label></div>
      {!sourceUrl ? <div className="panel-empty"><span className="empty-symbol">絵</span><p>Start with a manga page or panel image.</p><span>Images are processed by the local backend.</span></div> : <>
        <p className="crop-instruction">Drag the crop handles to select a single speech bubble.</p>
        <div className="crop-stage"><ReactCrop crop={crop} onChange={(pixelCrop) => setCrop(pixelCrop)} onComplete={(pixelCrop) => setCompletedCrop(pixelCrop)} keepSelection>
          <img ref={imageRef} src={sourceUrl} alt="Selected manga page. Drag a box over one bubble to crop it." onLoad={() => { setCompletedCrop(null); setCrop(undefined); }} />
        </ReactCrop></div>
        <div className="panel-action-row"><p className="panel-note">The crop is sent to your local `/ocr` endpoint.</p><button className="render-button" onClick={readBubble} disabled={reading || processing}>{reading ? <><span className="spinner" />Reading</> : "Read bubble"}</button></div>
      </>}
      {ocrText !== "" && <div className="ocr-result"><label htmlFor="ocr-text">Recognized text — edit any OCR errors</label><textarea id="ocr-text" className="text-input" lang="ja" value={ocrText} onChange={(event) => setOcrText(event.target.value)} spellCheck="false" /></div>}
      {error && <ErrorMessage message={error} />}
      <div className="panel-process-row"><p className="panel-note">Process sends this text through the existing kanji masking and reading view.</p><button className="render-button" onClick={processText} disabled={!ocrText.trim() || processing || reading}>{processing ? <><span className="spinner" />Processing</> : "Process text"}</button></div>
    </section>
    <footer className="page-footer"><span>Your crop is saved with cards created from this text.</span><span className="footer-dot">·</span><span>Offline after setup</span></footer>
  </main>;
}

function LookupPanel({ token, sentence, data, loading, error, saveState, showOriginal, onShowOriginal, onClose, knownKanji, savedWords, lexicalPos, onWordClick, onSaveExample }) {
  const word = token.masked && !showOriginal ? token.display : token.surface;
  return <aside className="lookup-panel" aria-label="Word lookup">
    <div className="lookup-topline"><div><p className="eyebrow">WORD LOOKUP</p><h2 lang="ja">{word}</h2></div><button className="close-button" onClick={onClose} aria-label="Close lookup">×</button></div>
    {token.masked && <label className="original-toggle"><input type="checkbox" checked={showOriginal} onChange={(event) => onShowOriginal(event.target.checked)} />Show original</label>}
    <div className="lookup-meta"><span lang="ja">{token.reading_hiragana || "Reading unavailable"}</span><span>{token.pos || "Part of speech unavailable"}</span></div>
    {saveState?.status === "saving" && <p className="saved-indicator" role="status">Saving this word…</p>}
    {saveState?.status === "saved" && <p className="saved-indicator" role="status">✓ Saved{saveState.created ? " to Cards" : ` · tapped ${saveState.card.tap_count} times`}</p>}
    {saveState?.status === "error" && <p className="save-error" role="alert">Couldn’t save this word: {saveState.message}</p>}
    {loading && <p className="lookup-status">Looking in your local dictionary…</p>}
    {error && <ErrorMessage message={error} />}
    {data && !data.found && <p className="lookup-status">No exact dictionary entry was found.</p>}
    {data?.found && <div className="lookup-content">{(data.entries || []).map((entry, index) => <article className="dictionary-entry" key={`${entry.kanji_forms?.join("")}-${index}`}>
      <p className="entry-forms" lang="ja">{entry.kanji_forms?.join("、") || entry.kana_forms?.join("、") || word}<span>{entry.kana_forms?.join("、")}</span></p>
      {entry.common && <span className="common-badge">Common</span>}
      {(entry.senses || []).map((sense, senseIndex) => <div className="sense" key={senseIndex}><p className="sense-pos">{sense.pos?.join(", ") || "Meaning"}</p><ul>{sense.glosses?.map((gloss, glossIndex) => <li key={glossIndex}>{gloss}</li>)}</ul></div>)}
    </article>)}
    {(data.kanji || []).length > 0 && <section className="kanji-breakdown"><p className="eyebrow">KANJI BREAKDOWN</p>{data.kanji.map((item) => <article className="kanji-detail" key={item.char}><strong lang="ja">{item.char}</strong><div><p>{item.meanings?.join(", ") || "Meaning unavailable"}</p><span>On: {item.onyomi?.join("、") || "—"} · Kun: {item.kunyomi?.join("、") || "—"}{item.strokes ? ` · ${item.strokes} strokes` : ""}</span></div></article>)}</section>}</div>}
    <TutorPanel
      token={token}
      sentence={sentence}
      knownKanji={knownKanji}
      savedWords={savedWords}
      lexicalPos={lexicalPos}
      onWordClick={onWordClick}
      onSaveExample={onSaveExample}
    />
  </aside>;
}

function TutorPanel({ token, sentence, knownKanji, savedWords, lexicalPos, onWordClick, onSaveExample }) {
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState("");
  const [lastMode, setLastMode] = useState("");
  const [result, setResult] = useState(null);
  const [renderedText, setRenderedText] = useState([]);
  const [practice, setPractice] = useState([]);
  const [error, setError] = useState("");
  const [savingSentence, setSavingSentence] = useState("");
  const [practiceLemma, setPracticeLemma] = useState("");
  const [savedExamples, setSavedExamples] = useState(() => new Set());
  const [saveError, setSaveError] = useState("");
  const targetWord = token.lemma || token.surface;

  async function run(action) {
    setMode(action);
    setLastMode(action);
    setBusy(true);
    setError("");
    setSaveError("");
    setResult(null);
    setRenderedText([]);
    setPractice([]);
    if (action === "practice") setPracticeLemma(targetWord);
    try {
      const latest = await request("/cards");
      const words = [...new Set([
        ...savedWords,
        ...(latest.cards || []).map((card) => card.lemma),
        targetWord,
      ])];
      let generated;
      if (action === "explain") {
        generated = await request("/explain", {
          method: "POST",
          body: JSON.stringify({ sentence, word: targetWord, known_kanji: knownKanji, known_words: words }),
        });
      } else if (action === "practice") {
        generated = await request("/practice", {
          method: "POST",
          body: JSON.stringify({ word: targetWord, known_kanji: knownKanji, known_words: words, count: 3 }),
        });
      } else {
        generated = await request("/explain-casual", {
          method: "POST",
          body: JSON.stringify({ sentence, known_kanji: knownKanji, known_words: words }),
        });
      }

      setResult(generated);
      if (action === "practice") {
        const rendered = await Promise.all((generated.sentences || []).map(async (item) => {
          const output = await request("/render", {
            method: "POST",
            body: JSON.stringify({ text: item.sentence, known_kanji: knownKanji }),
          });
          return { ...item, tokens: output.tokens || [] };
        }));
        setPractice(rendered);
      } else if (generated.explanation_ja) {
        const output = await request("/render", {
          method: "POST",
          body: JSON.stringify({ text: generated.explanation_ja, known_kanji: knownKanji }),
        });
        setRenderedText(output.tokens || []);
      }
    } catch (reason) {
      setError(reason.message);
    } finally {
      setBusy(false);
    }
  }

  async function saveExample(example) {
    setSavingSentence(example);
    setSaveError("");
    try {
      await onSaveExample(practiceLemma || targetWord, example);
      setSavedExamples((current) => new Set([...current, example]));
    } catch (reason) {
      setSaveError(reason.message);
    } finally {
      setSavingSentence("");
    }
  }

  return <section className="tutor-section" aria-label="AI tutor">
    <div className="tutor-heading"><div><p className="eyebrow">LOCAL AI TUTOR</p><h3>Learn this word</h3></div></div>
    <div className="tutor-actions">
      <button className="secondary-button" onClick={() => run("explain")} disabled={busy}>AI explain</button>
      <button className="secondary-button" onClick={() => run("practice")} disabled={busy}>Practice sentences</button>
      <button className="secondary-button" onClick={() => run("casual")} disabled={busy}>Explain casual speech</button>
    </div>
    {busy && <p className="tutor-loading" role="status"><span className="spinner tutor-spinner" />The local tutor is thinking…</p>}
    {error && <div className="tutor-error"><ErrorMessage message={error} /><button className="text-button" onClick={() => run(lastMode)}>Retry</button></div>}
    {result && <>
      <p className={`level-check${result.passed ? " is-passed" : " is-review"}`} role="status">
        Level-checked · {result.tries} {result.tries === 1 ? "try" : "tries"} · {result.passed ? "Passed" : "Needs review"}
      </p>
      {mode === "practice" ? <div className="tutor-practice-list">{practice.map((item, index) => <article className="tutor-practice-item" key={`${index}-${item.sentence}`}>
        <div className="tutor-japanese" lang="ja"><TokenRun tokens={item.tokens} lexicalPos={lexicalPos} onTokenClick={onWordClick} /></div>
        <p className="tutor-hint">{item.hint_en}</p>
        {savedExamples.has(item.sentence) ? <span className="example-saved">Saved to card</span> : <button className="text-button save-example-button" onClick={() => saveExample(item.sentence)} disabled={savingSentence === item.sentence}>{savingSentence === item.sentence ? "Saving…" : "Save as card example"}</button>}
      </article>)}</div> : <div className="tutor-explanation">
        <p className="tutor-japanese" lang="ja"><TokenRun tokens={renderedText} lexicalPos={lexicalPos} onTokenClick={onWordClick} /></p>
        <p className="tutor-hint">{result.hint_en}</p>
      </div>}
      {result.passed === false && <button className="text-button" onClick={() => run(lastMode)} disabled={busy}>Try again</button>}
    </>}
    {saveError && <ErrorMessage message={saveError} />}
  </section>;
}

export default App;
