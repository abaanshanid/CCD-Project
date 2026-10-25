import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  ArrowDownToLine,
  Check,
  ChevronDown,
  Copy,
  Crop,
  FileImage,
  FlipHorizontal2,
  ImageMinus,
  LoaderCircle,
  Maximize2,
  RefreshCw,
  RotateCw,
  Settings2,
  Trash2,
  UploadCloud,
  ArrowRight,
  X,
} from "lucide-react";

const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const TERMINAL_STATUSES = new Set(["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"]);
const ACCEPTED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

const wait = (milliseconds) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds));

function humanSize(bytes = 0) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function apiErrorMessage(error) {
  if (typeof error?.detail === "string") return error.detail;
  if (error?.detail?.message) return error.detail.message;
  return error?.message || "Something went wrong.";
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, options);
  const body = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(apiErrorMessage(body));
  }

  return body;
}

function FileCard({ entry, onRemove, disabled }) {
  return (
    <article className="file-card">
      <img src={entry.preview} alt={entry.file.name} />
      <div className="file-copy">
        <strong title={entry.file.name}>{entry.file.name}</strong>
        <span>{humanSize(entry.file.size)}</span>
      </div>
      <button
        type="button"
        className="icon-button"
        aria-label={`Remove ${entry.file.name}`}
        onClick={() => onRemove(entry.id)}
        disabled={disabled}
      >
        <X size={17} />
      </button>
    </article>
  );
}

function SelectField({ label, icon: Icon, value, onChange, children, disabled }) {
  return (
    <label className="field select-field">
      <span><Icon size={15} /> {label}</span>
      <div className="select-wrap">
        <select value={value} onChange={onChange} disabled={disabled}>
          {children}
        </select>
        <ChevronDown size={15} />
      </div>
    </label>
  );
}

function ResultCard({ image, duplicateKind }) {
  const complete = image.status === "COMPLETED";

  return (
    <article className={`result-card ${duplicateKind ? "is-duplicate" : ""}`}>
      <div className="result-preview">
        {complete ? (
          <img src={image.downloadUrl} alt={image.filename} />
        ) : (
          <div className="result-placeholder"><AlertCircle /></div>
        )}
        <span className={`status-pill status-${image.status?.toLowerCase()}`}>
          {complete ? <Check size={12} /> : <AlertCircle size={12} />}
          {image.status}
        </span>
        {duplicateKind && (
          <span className={`duplicate-badge ${duplicateKind.toLowerCase()}`}>
            <Copy size={12} /> {duplicateKind}
          </span>
        )}
      </div>
      <div className="result-copy">
        <div>
          <strong title={image.filename}>{image.filename}</strong>
          <span>
            {image.outputFormat || "—"}
            {image.outputSize ? ` · ${humanSize(image.outputSize)}` : ""}
          </span>
        </div>
        {complete ? (
          <a
            className="download-button"
            href={image.downloadUrl}
            target="_blank"
            rel="noreferrer"
          >
            <ArrowDownToLine size={16} /> Download
          </a>
        ) : (
          <p className="image-error">{image.error || "Processing failed"}</p>
        )}
      </div>
    </article>
  );
}

export default function App() {
  const inputRef = useRef(null);
  const filesRef = useRef([]);
  const [files, setFiles] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [message, setMessage] = useState("");
  const [uploadedCount, setUploadedCount] = useState(0);
  const [result, setResult] = useState(null);
  const [batchId, setBatchId] = useState("");
  const [resizeEnabled, setResizeEnabled] = useState(false);
  const [options, setOptions] = useState({
    width: 1280,
    height: 720,
    maintainAspectRatio: true,
    rotate: "",
    flip: "",
    crop: "",
    removeBackground: false,
    outputFormat: "WEBP",
    quality: 85,
    duplicateThreshold: 5,
  });

  const busy = ["creating", "uploading", "starting", "processing"].includes(phase);

  useEffect(() => {
    filesRef.current = files;
  }, [files]);

  useEffect(() => {
    return () => filesRef.current.forEach((entry) => URL.revokeObjectURL(entry.preview));
  }, []);

  const duplicateKinds = useMemo(() => {
    const kinds = new Map();
    const duplicates = result?.duplicates;

    duplicates?.exact_duplicates?.forEach((pair) => {
      kinds.set(pair.originalImageId, "EXACT");
      kinds.set(pair.duplicateImageId, "EXACT");
    });

    duplicates?.similar_images?.forEach((pair) => {
      if (!kinds.has(pair.firstImageId)) kinds.set(pair.firstImageId, "SIMILAR");
      if (!kinds.has(pair.secondImageId)) kinds.set(pair.secondImageId, "SIMILAR");
    });

    return kinds;
  }, [result]);

  const progress = result?.total
    ? Math.round(((result.completed + result.failed) / result.total) * 100)
    : phase === "uploading" && files.length
      ? Math.round((uploadedCount / files.length) * 100)
      : phase === "processing"
        ? 8
        : 0;

  function setOption(name, value) {
    setOptions((current) => ({ ...current, [name]: value }));
  }

  function addFiles(incoming) {
    const valid = Array.from(incoming).filter((file) => ACCEPTED_TYPES.has(file.type));
    setMessage(valid.length !== incoming.length ? "Unsupported files were ignored." : "");

    setFiles((current) => {
      const existing = new Set(current.map((entry) => `${entry.file.name}-${entry.file.size}`));
      const additions = valid
        .filter((file) => !existing.has(`${file.name}-${file.size}`))
        .slice(0, Math.max(0, 50 - current.length))
        .map((file) => ({
          id: crypto.randomUUID(),
          file,
          preview: URL.createObjectURL(file),
        }));
      return [...current, ...additions];
    });
  }

  function removeFile(id) {
    setFiles((current) => {
      const removed = current.find((entry) => entry.id === id);
      if (removed) URL.revokeObjectURL(removed.preview);
      return current.filter((entry) => entry.id !== id);
    });
  }

  function reset() {
    files.forEach((entry) => URL.revokeObjectURL(entry.preview));
    setFiles([]);
    setResult(null);
    setBatchId("");
    setUploadedCount(0);
    setMessage("");
    setPhase("idle");
  }

  async function pollBatch(id) {
    const deadline = Date.now() + 10 * 60 * 1000;

    while (Date.now() < deadline) {
      const latest = await request(`/batches/${id}`);
      setResult(latest);

      const imagesDone = TERMINAL_STATUSES.has(latest.status);
      const duplicatesDone = ["COMPLETED", "FAILED"].includes(latest.duplicateStatus);

      if (imagesDone && duplicatesDone) return latest;
      await wait(2500);
    }

    throw new Error("Processing is taking longer than expected. You can refresh the batch later.");
  }

  async function processBatch() {
    if (!API_URL) {
      setMessage("Add VITE_API_URL to your .env file first.");
      return;
    }
    if (!files.length) {
      setMessage("Choose at least one image.");
      return;
    }
    if (options.removeBackground && ["JPEG", "JPG"].includes(options.outputFormat)) {
      setMessage("Choose PNG or WEBP to preserve a transparent background.");
      return;
    }

    setResult(null);
    setMessage("");
    setUploadedCount(0);

    try {
      setPhase("creating");
      const operations = {
        rotate: options.rotate === "" ? null : Number(options.rotate),
        flip: options.flip || null,
        crop: options.crop || null,
        remove_background: options.removeBackground,
        output_format: options.outputFormat,
        quality: Number(options.quality),
        duplicate_threshold: Number(options.duplicateThreshold),
      };

      if (resizeEnabled) {
        operations.resize = {
          width: Number(options.width),
          height: Number(options.height),
          maintain_aspect_ratio: options.maintainAspectRatio,
        };
      }

      const batch = await request("/batches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          files: files.map(({ file }) => ({
            filename: file.name,
            content_type: file.type || "application/octet-stream",
          })),
          operations,
        }),
      });

      setBatchId(batch.batchId);
      setPhase("uploading");

      for (let index = 0; index < batch.uploads.length; index += 1) {
        const upload = batch.uploads[index];
        const response = await fetch(upload.uploadUrl, {
          method: "PUT",
          headers: upload.headers,
          body: files[index].file,
        });

        if (!response.ok) throw new Error(`Upload failed for ${files[index].file.name}.`);
        setUploadedCount(index + 1);
      }

      setPhase("starting");
      await request(`/batches/${batch.batchId}/start`, { method: "POST" });
      setPhase("processing");

      const completed = await pollBatch(batch.batchId);
      setPhase(completed.failed ? "completed-errors" : "completed");
    } catch (error) {
      setMessage(error.message);
      setPhase("error");
    }
  }

  return (
    <div className="app-shell">
      <main>
        <nav className="app-nav" aria-label="Main navigation">
          <span>Batch image processor</span>
        </nav>

        <section className="workspace-grid">
          <div className="panel upload-panel">
            <div className="panel-heading">
              <div><span className="section-index">01</span><h2>Images</h2></div>
              <span className="panel-meta">SOURCE FILES</span>
            </div>

            <button
              className={`dropzone ${dragging ? "is-dragging" : ""} ${files.length ? "has-files" : ""}`}
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                if (!busy) addFiles(event.dataTransfer.files);
              }}
            >
              <input
                ref={inputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                multiple
                onChange={(event) => {
                  addFiles(event.target.files);
                  event.target.value = "";
                }}
              />
              <span className="upload-icon"><UploadCloud size={27} /></span>
              <strong>Drop your images here</strong>
              <span>or click to browse from your computer</span>
            </button>

            {files.length > 0 && (
              <div className="file-section">
                <div className="file-section-head">
                  <span>{files.length} image{files.length === 1 ? "" : "s"} selected</span>
                  <button type="button" onClick={reset} disabled={busy}>
                    <Trash2 size={14} /> Clear all
                  </button>
                </div>
                <div className="file-grid">
                  {files.map((entry) => (
                    <FileCard key={entry.id} entry={entry} onRemove={removeFile} disabled={busy} />
                  ))}
                </div>
              </div>
            )}
          </div>

          <aside className="panel settings-panel">
            <div className="panel-heading">
              <div><span className="section-index">02</span><h2>Settings</h2></div>
              <Settings2 size={18} className="muted-icon" />
            </div>

            <div className="settings-stack">
              <div className="setting-block">
                <label className="toggle-row">
                  <span><Maximize2 size={16} /><span><strong>Resize</strong><small>Set target dimensions</small></span></span>
                  <input
                    type="checkbox"
                    checked={resizeEnabled}
                    onChange={(event) => setResizeEnabled(event.target.checked)}
                    disabled={busy}
                  />
                  <i />
                </label>
                {resizeEnabled && (
                  <div className="size-grid">
                    <label><span>Width</span><input type="number" min="1" value={options.width} onChange={(e) => setOption("width", e.target.value)} disabled={busy} /></label>
                    <span>×</span>
                    <label><span>Height</span><input type="number" min="1" value={options.height} onChange={(e) => setOption("height", e.target.value)} disabled={busy} /></label>
                    <label className="check-row"><input type="checkbox" checked={options.maintainAspectRatio} onChange={(e) => setOption("maintainAspectRatio", e.target.checked)} disabled={busy} /> Keep aspect ratio</label>
                  </div>
                )}
              </div>

              <div className="field-grid">
                <SelectField label="Rotate" icon={RotateCw} value={options.rotate} onChange={(e) => setOption("rotate", e.target.value)} disabled={busy}>
                  <option value="">None</option><option value="90">90°</option><option value="180">180°</option><option value="270">270°</option>
                </SelectField>
                <SelectField label="Flip" icon={FlipHorizontal2} value={options.flip} onChange={(e) => setOption("flip", e.target.value)} disabled={busy}>
                  <option value="">None</option><option value="horizontal">Horizontal</option><option value="vertical">Vertical</option>
                </SelectField>
                <SelectField label="Crop" icon={Crop} value={options.crop} onChange={(e) => setOption("crop", e.target.value)} disabled={busy}>
                  <option value="">None</option><option value="1:1">1:1 Square</option><option value="4:3">4:3</option><option value="16:9">16:9</option>
                </SelectField>
                <SelectField label="Format" icon={FileImage} value={options.outputFormat} onChange={(e) => setOption("outputFormat", e.target.value)} disabled={busy}>
                  <option>WEBP</option><option>PNG</option><option>JPEG</option>
                </SelectField>
              </div>

              <label className="toggle-row standalone">
                <span><ImageMinus size={16} /><span><strong>Remove background</strong><small>Preserve transparency with PNG/WEBP</small></span></span>
                <input type="checkbox" checked={options.removeBackground} onChange={(e) => setOption("removeBackground", e.target.checked)} disabled={busy} />
                <i />
              </label>

              <label className="range-field">
                <span><span>Output quality</span><strong>{options.quality}%</strong></span>
                <input type="range" min="1" max="100" value={options.quality} onChange={(e) => setOption("quality", e.target.value)} disabled={busy} />
              </label>

              <label className="range-field">
                <span><span>Visual duplicate sensitivity</span><strong>{options.duplicateThreshold}</strong></span>
                <input type="range" min="0" max="20" value={options.duplicateThreshold} onChange={(e) => setOption("duplicateThreshold", e.target.value)} disabled={busy} />
                <small>Higher values flag more images as visually similar.</small>
              </label>
            </div>

            <button className="process-button" type="button" onClick={processBatch} disabled={busy || !files.length}>
              {busy ? <LoaderCircle className="spin" size={18} /> : <ArrowRight size={18} />}
              {phase === "creating" && "Creating batch…"}
              {phase === "uploading" && `Uploading ${uploadedCount}/${files.length}…`}
              {phase === "starting" && "Starting workers…"}
              {phase === "processing" && "Processing images…"}
              {!busy && "Process batch"}
            </button>

            {message && <div className="error-banner"><AlertCircle size={16} /> {message}</div>}
          </aside>
        </section>

        {(busy || result) && (
          <section className="panel progress-panel">
            <div className="progress-copy">
              <span className={`progress-icon ${phase}`}>
                {TERMINAL_STATUSES.has(result?.status) ? <Check size={20} /> : <LoaderCircle className="spin" size={20} />}
              </span>
              <div>
                <strong>{result?.status?.replaceAll("_", " ") || phase.replaceAll("-", " ")}</strong>
                <span>{batchId ? `Batch ${batchId.slice(0, 10)}…` : "Preparing cloud job"}</span>
              </div>
            </div>
            <div className="progress-track"><span style={{ width: `${progress}%` }} /></div>
            <strong className="progress-number">{progress}%</strong>
          </section>
        )}

        {result && TERMINAL_STATUSES.has(result.status) && (
          <section className="results-section">
            <div className="results-heading">
              <div>
                <h2>Processed images</h2>
                <p>{result.completed} completed · {result.failed} failed · {duplicateKinds.size} duplicate-highlighted images</p>
              </div>
              <button className="secondary-button" type="button" onClick={reset}><RefreshCw size={16} /> New batch</button>
            </div>

            {(result.duplicates?.exact_duplicates?.length > 0 || result.duplicates?.similar_images?.length > 0) && (
              <div className="duplicate-report">
                <div className="report-title"><Copy size={18} /><div><strong>Duplicates found</strong><span>They are highlighted below and were still processed.</span></div></div>
                <div className="report-pairs">
                  {result.duplicates.exact_duplicates.map((pair) => (
                    <span key={`${pair.originalImageId}-${pair.duplicateImageId}`}><b>Exact</b> {pair.original} ↔ {pair.duplicate}</span>
                  ))}
                  {result.duplicates.similar_images.map((pair) => (
                    <span key={`${pair.firstImageId}-${pair.secondImageId}`}><b>Similar · {pair.distance}</b> {pair.first} ↔ {pair.second}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="result-grid">
              {result.images.map((image) => (
                <ResultCard key={image.imageId} image={image} duplicateKind={duplicateKinds.get(image.imageId)} />
              ))}
            </div>
          </section>
        )}
      </main>
    </div>
  );
}
