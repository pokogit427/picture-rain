import { useEffect, useRef, useState, type PointerEvent } from "react";
import { cancelDraft, getAssetUrl, getDraft, saveDraft, submitRound, uploadLayer, type InboxItem } from "../api";

export type Point = { x: number; y: number };
export type Stroke = { points: Point[]; color: string; width: number };
type ToolMode = "select" | "brush" | "eraser";
export type EditorLayer = {
  id: string;
  kind: "sticker" | "text" | "image";
  value: string;
  x: number;
  y: number;
  scale: number;
  rotation: number;
  color: string;
  assetUrl?: string;
  assetId?: string;
};
type EditorSnapshot = { strokes: Stroke[]; layers: EditorLayer[] };
export type EditorDocument = {
  strokes: Stroke[];
  layers: EditorLayer[];
  rotation: number;
  brightness: number;
  cropSquare: boolean;
};

interface EditorCanvasProps {
  item: InboxItem;
}

const BRUSH_COLOR = "#ffde8a";
const STICKERS = ["😂", "❤️", "✨", "🐶", "😎"];

function drawScene(
  canvas: HTMLCanvasElement,
  image: HTMLImageElement,
  zoom: number,
  strokes: Stroke[],
  layers: EditorLayer[],
  activeStroke: Stroke | null,
  selectedLayerId: string | null,
  imageLayers: Map<string, HTMLImageElement>,
  rotation: number,
  brightness: number,
  cropSquare: boolean,
) {
  const sourceWidth = cropSquare ? Math.min(image.naturalWidth, image.naturalHeight) : image.naturalWidth;
  const sourceHeight = cropSquare ? Math.min(image.naturalWidth, image.naturalHeight) : image.naturalHeight;
  const rotated = Math.abs(rotation % 180) === 90;
  const baseWidth = rotated ? sourceHeight : sourceWidth;
  const baseHeight = rotated ? sourceWidth : sourceHeight;
  const fitScale = Math.min(960 / baseWidth, 640 / baseHeight, 1);
  const width = Math.max(1, Math.round(baseWidth * fitScale * zoom));
  const height = Math.max(1, Math.round(baseHeight * fitScale * zoom));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, width, height);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  const cropX = cropSquare ? (image.naturalWidth - sourceWidth) / 2 : 0;
  const cropY = cropSquare ? (image.naturalHeight - sourceHeight) / 2 : 0;
  context.save();
  context.translate(width / 2, height / 2);
  context.rotate((rotation * Math.PI) / 180);
  context.filter = `brightness(${brightness}%)`;
  context.drawImage(
    image,
    cropX,
    cropY,
    sourceWidth,
    sourceHeight,
    -sourceWidth * fitScale * zoom / 2,
    -sourceHeight * fitScale * zoom / 2,
    sourceWidth * fitScale * zoom,
    sourceHeight * fitScale * zoom,
  );
  context.restore();
  context.filter = "none";
  for (const stroke of activeStroke ? [...strokes, activeStroke] : strokes) {
    if (stroke.points.length < 2) continue;
    context.beginPath();
    context.moveTo(stroke.points[0].x * width, stroke.points[0].y * height);
    for (const point of stroke.points.slice(1)) context.lineTo(point.x * width, point.y * height);
    context.strokeStyle = stroke.color;
    context.lineWidth = stroke.width * Math.min(width, height);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.stroke();
  }
  for (const layer of layers) {
    const size = layer.scale * Math.min(width, height);
    context.save();
    context.translate(layer.x * width, layer.y * height);
    context.rotate((layer.rotation * Math.PI) / 180);
    let boxWidth = size;
    let boxHeight = size;
    if (layer.kind === "image") {
      const layerImage = imageLayers.get(layer.id);
      if (layerImage) {
        const ratio = layerImage.naturalWidth / layerImage.naturalHeight;
        boxWidth = ratio >= 1 ? size : size * ratio;
        boxHeight = ratio >= 1 ? size / ratio : size;
        context.drawImage(layerImage, -boxWidth / 2, -boxHeight / 2, boxWidth, boxHeight);
      }
    } else {
      context.textAlign = "center";
      context.textBaseline = "middle";
      context.font = `${size}px "Apple Color Emoji", "Segoe UI Emoji", sans-serif`;
      context.fillStyle = layer.color;
      context.fillText(layer.value, 0, 0);
      const bounds = context.measureText(layer.value);
      boxWidth = bounds.width;
    }
    if (layer.id === selectedLayerId) {
      context.strokeStyle = "#b9a8ff";
      context.lineWidth = 2;
      context.setLineDash([5, 4]);
      context.strokeRect(-boxWidth / 2 - 8, -boxHeight / 2 - 8, boxWidth + 16, boxHeight + 16);
      context.setLineDash([]);
    }
    context.restore();
  }
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function newLayer(kind: EditorLayer["kind"], value: string): EditorLayer {
  return {
    id: crypto.randomUUID(),
    kind,
    value,
    x: 0.5,
    y: 0.5,
    scale: kind === "text" ? 0.055 : kind === "image" ? 0.28 : 0.12,
    rotation: 0,
    color: kind === "text" ? "#ffffff" : "#ffffff",
  };
}

export function EditorCanvas({ item }: EditorCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const imageLayersRef = useRef(new Map<string, HTMLImageElement>());
  const dragRef = useRef<{ id: string; offset: Point; start: EditorSnapshot } | null>(null);
  const eraseBaseRef = useRef<Stroke[] | null>(null);
  const [zoom, setZoom] = useState(1);
  const [imageState, setImageState] = useState<"loading" | "ready" | "error">("loading");
  const [mode, setMode] = useState<ToolMode>("select");
  const [past, setPast] = useState<EditorSnapshot[]>([]);
  const [present, setPresent] = useState<Stroke[]>([]);
  const [layers, setLayers] = useState<EditorLayer[]>([]);
  const [future, setFuture] = useState<EditorSnapshot[]>([]);
  const [activeStroke, setActiveStroke] = useState<Stroke | null>(null);
  const [selectedLayerId, setSelectedLayerId] = useState<string | null>(null);
  const [textValue, setTextValue] = useState("");
  const [customEmoji, setCustomEmoji] = useState("");
  const [uploadingLayer, setUploadingLayer] = useState(false);
  const [layerError, setLayerError] = useState<string | null>(null);
  const [imageVersion, setImageVersion] = useState(0);
  const [rotation, setRotation] = useState(0);
  const [brightness, setBrightness] = useState(100);
  const [cropSquare, setCropSquare] = useState(false);
  const [draftState, setDraftState] = useState<"loading" | "idle" | "dirty" | "saving" | "saved" | "error">("loading");
  const [draftVersion, setDraftVersion] = useState(1);
  const [draftError, setDraftError] = useState<string | null>(null);
  const [submissionState, setSubmissionState] = useState<"ready" | "submitting" | "submitted" | "error">("ready");
  const hydratingDraftRef = useRef(true);
  const suppressDirtyRef = useRef(false);

  const currentSnapshot = (): EditorSnapshot => ({ strokes: present, layers });

  function loadImageLayers(nextLayers: EditorLayer[]) {
    imageLayersRef.current.clear();
    for (const layer of nextLayers.filter((candidate) => candidate.kind === "image")) {
      const source = layer.assetUrl ?? (layer.assetId ? getAssetUrl(`/assets/${layer.assetId}/content`) : null);
      if (!source) continue;
      layer.assetUrl = source;
      const layerImage = new Image();
      layerImage.onload = () => {
        imageLayersRef.current.set(layer.id, layerImage);
        setImageVersion((version) => version + 1);
      };
      layerImage.src = source;
    }
  }

  useEffect(() => {
    let active = true;
    hydratingDraftRef.current = true;
    setDraftError(null);
    setSubmissionState("ready");
    const draftPromise = getDraft(item.round_id).catch((reason: unknown) => {
      if (active) setDraftError(reason instanceof Error ? reason.message : "초안을 불러오지 못했어요.");
      return null;
    });
    const image = new Image();
    image.decoding = "async";
    image.onload = async () => {
      if (!active) return;
      imageRef.current = image;
      setPresent([]);
      setLayers([]);
      setPast([]);
      setFuture([]);
      setSelectedLayerId(null);
      imageLayersRef.current.clear();
      setRotation(0);
      setBrightness(100);
      setCropSquare(false);
      setImageState("ready");
      const draft = await draftPromise;
      if (!active) return;
      suppressDirtyRef.current = true;
      if (draft) {
        const document = draft.document as EditorDocument;
        const nextLayers = Array.isArray(document.layers) ? document.layers : [];
        setPresent(Array.isArray(document.strokes) ? document.strokes : []);
        setLayers(nextLayers);
        setRotation(typeof document.rotation === "number" ? document.rotation : 0);
        setBrightness(typeof document.brightness === "number" ? document.brightness : 100);
        setCropSquare(document.cropSquare === true);
        setDraftVersion(draft.version);
        loadImageLayers(nextLayers);
        setDraftState("saved");
      } else {
        setDraftVersion(1);
        setDraftState("idle");
      }
      hydratingDraftRef.current = false;
    };
    image.onerror = () => {
      if (!active) return;
      hydratingDraftRef.current = false;
      setImageState("error");
      setDraftState("error");
    };
    image.src = getAssetUrl(item.input.url);
    return () => {
      active = false;
      image.onload = null;
      image.onerror = null;
    };
  }, [item]);

  useEffect(() => {
    if (suppressDirtyRef.current) {
      suppressDirtyRef.current = false;
      return;
    }
    if (imageState === "ready" && !hydratingDraftRef.current) setDraftState("dirty");
  }, [present, layers, rotation, brightness, cropSquare, imageState]);

  useEffect(() => {
    if (imageRef.current && canvasRef.current) {
      drawScene(canvasRef.current, imageRef.current, zoom, present, layers, activeStroke, selectedLayerId, imageLayersRef.current, rotation, brightness, cropSquare);
    }
  }, [zoom, present, layers, activeStroke, selectedLayerId, rotation, brightness, cropSquare, imageVersion]);

  function pointFromEvent(event: PointerEvent<HTMLCanvasElement>): Point {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const bounds = canvas.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  }

  function findLayer(point: Point): EditorLayer | undefined {
    return [...layers].reverse().find((layer) => distance({ x: layer.x, y: layer.y }, point) < Math.max(0.08, layer.scale * 1.4));
  }

  function handlePointerDown(event: PointerEvent<HTMLCanvasElement>) {
    if (imageState !== "ready") return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointFromEvent(event);
    if (mode === "select") {
      const layer = findLayer(point);
      setSelectedLayerId(layer?.id ?? null);
      if (layer) dragRef.current = { id: layer.id, offset: { x: point.x - layer.x, y: point.y - layer.y }, start: currentSnapshot() };
      return;
    }
    if (mode === "eraser") {
      eraseBaseRef.current = present;
      return;
    }
    setFuture([]);
    setActiveStroke({ points: [point], color: BRUSH_COLOR, width: 0.012 });
  }

  function handlePointerMove(event: PointerEvent<HTMLCanvasElement>) {
    const point = pointFromEvent(event);
    if (mode === "select" && dragRef.current) {
      const drag = dragRef.current;
      setLayers((current) => current.map((layer) => layer.id === drag.id ? { ...layer, x: point.x - drag.offset.x, y: point.y - drag.offset.y } : layer));
      return;
    }
    if (mode === "eraser") {
      if (!eraseBaseRef.current) return;
      setPresent((current) => {
        const filtered = current.filter((stroke) => !stroke.points.some((candidate) => distance(candidate, point) < 0.045));
        if (filtered.length !== current.length && eraseBaseRef.current === current) {
          setPast((history) => [...history, { strokes: current, layers }]);
          setFuture([]);
          eraseBaseRef.current = filtered;
        }
        return filtered;
      });
      return;
    }
    setActiveStroke((current) => current ? { ...current, points: [...current.points, point] } : current);
  }

  function finishPointer(event: PointerEvent<HTMLCanvasElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (mode === "select") {
      if (dragRef.current) setPast((history) => [...history, dragRef.current!.start]);
      dragRef.current = null;
      return;
    }
    if (mode === "eraser") {
      eraseBaseRef.current = null;
      return;
    }
    setActiveStroke((stroke) => {
      if (!stroke || stroke.points.length < 2) return null;
      setPast((history) => [...history, currentSnapshot()]);
      return null;
    });
  }

  function commitLayers(nextLayers: EditorLayer[]) {
    setPast((history) => [...history, currentSnapshot()]);
    setFuture([]);
    setLayers(nextLayers);
  }

  function addSticker(value: string) {
    const layer = newLayer("sticker", value);
    commitLayers([...layers, layer]);
    setSelectedLayerId(layer.id);
    setMode("select");
  }

  function addText() {
    if (!textValue.trim()) return;
    const layer = newLayer("text", textValue.trim().slice(0, 40));
    commitLayers([...layers, layer]);
    setSelectedLayerId(layer.id);
    setTextValue("");
    setMode("select");
  }

  function addCustomEmoji() {
    const emoji = customEmoji.trim();
    if (!emoji || Array.from(emoji).length > 12) return;
    const layer = newLayer("sticker", emoji);
    commitLayers([...layers, layer]);
    setSelectedLayerId(layer.id);
    setCustomEmoji("");
    setMode("select");
  }

  async function addImageFromFile(file: File) {
    setUploadingLayer(true);
    setLayerError(null);
    try {
      const asset = await uploadLayer(item.round_id, file);
      const layer = newLayer("image", "");
      layer.assetId = asset.id;
      layer.assetUrl = getAssetUrl(asset.url);
      const layerImage = new Image();
      layerImage.onload = () => {
        imageLayersRef.current.set(layer.id, layerImage);
        setImageVersion((version) => version + 1);
      };
      layerImage.src = layer.assetUrl;
      commitLayers([...layers, layer]);
      setSelectedLayerId(layer.id);
      setMode("select");
    } catch (reason) {
      setLayerError(reason instanceof Error ? reason.message : "사진 레이어를 추가하지 못했어요.");
    } finally {
      setUploadingLayer(false);
    }
  }

  function updateSelected(changes: Partial<EditorLayer>) {
    if (!selectedLayerId) return;
    commitLayers(layers.map((layer) => layer.id === selectedLayerId ? { ...layer, ...changes } : layer));
  }

  function deleteSelected() {
    if (!selectedLayerId) return;
    commitLayers(layers.filter((layer) => layer.id !== selectedLayerId));
    setSelectedLayerId(null);
  }

  function undo() {
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    setFuture((history) => [currentSnapshot(), ...history]);
    setPresent(previous.strokes);
    setLayers(previous.layers);
    setPast(past.slice(0, -1));
  }

  function redo() {
    if (future.length === 0) return;
    const next = future[0];
    setPast((history) => [...history, currentSnapshot()]);
    setPresent(next.strokes);
    setLayers(next.layers);
    setFuture(future.slice(1));
  }

  function currentDocument(): EditorDocument {
    return { strokes: present, layers, rotation, brightness, cropSquare };
  }

  function canvasBlob(): Promise<Blob | null> {
    return new Promise((resolve) => {
      const canvas = canvasRef.current;
      if (!canvas) {
        resolve(null);
        return;
      }
      canvas.toBlob(resolve, "image/png");
    });
  }

  async function saveCurrentDraft(): Promise<boolean> {
    if (draftState === "saving" || imageState !== "ready") return false;
    setDraftState("saving");
    setDraftError(null);
    try {
      const response = await saveDraft(
        item.round_id,
        JSON.stringify(currentDocument()),
        await canvasBlob(),
        draftVersion,
      );
      setDraftVersion(response.version);
      setDraftState("saved");
      return true;
    } catch (reason) {
      setDraftState("error");
      setDraftError(reason instanceof Error ? reason.message : "초안을 저장하지 못했어요.");
      return false;
    }
  }

  async function submitCurrentDraft() {
    if (submissionState === "submitting" || submissionState === "submitted") return;
    setSubmissionState("submitting");
    setDraftError(null);
    if (!(await saveCurrentDraft())) {
      setSubmissionState("error");
      return;
    }
    try {
      await submitRound(item.round_id);
      setSubmissionState("submitted");
      setDraftState("saved");
    } catch (reason) {
      setSubmissionState("error");
      setDraftError(reason instanceof Error ? reason.message : "완료 제출에 실패했어요.");
    }
  }

  async function removeDraft() {
    if (draftState === "saving" || submissionState === "submitted") return;
    try {
      await cancelDraft(item.round_id);
      suppressDirtyRef.current = true;
      setPresent([]);
      setLayers([]);
      setRotation(0);
      setBrightness(100);
      setCropSquare(false);
      setSelectedLayerId(null);
      imageLayersRef.current.clear();
      setImageVersion((version) => version + 1);
      setDraftVersion(1);
      setDraftState("idle");
      setSubmissionState("ready");
      setDraftError(null);
    } catch (reason) {
      setDraftState("error");
      setDraftError(reason instanceof Error ? reason.message : "초안을 취소하지 못했어요.");
    }
  }

  const selectedLayer = layers.find((layer) => layer.id === selectedLayerId);

  return (
    <section className="editor-panel" aria-label="사진 편집 캔버스">
      <div className="editor-heading">
        <div><p className="eyebrow">EDITOR PREVIEW</p><h3>편집할 사진</h3></div>
        <span className="editor-size">{item.input.width} × {item.input.height}</span>
      </div>
      <div className="editor-toolbar" aria-label="편집 도구">
        <button className={mode === "select" ? "tool-button active" : "tool-button"} onClick={() => setMode("select")} type="button">↖ 선택</button>
        <button className={mode === "brush" ? "tool-button active" : "tool-button"} onClick={() => setMode("brush")} type="button">✎ 그리기</button>
        <button className={mode === "eraser" ? "tool-button active" : "tool-button"} onClick={() => setMode("eraser")} type="button">⌫ 선 지우기</button>
        <span className="tool-spacer" />
        <button className="tool-button" disabled={past.length === 0} onClick={undo} type="button">↶</button>
        <button className="tool-button" disabled={future.length === 0} onClick={redo} type="button">↷</button>
      </div>
      <div className="layer-toolbar">
        <span>스티커</span>
        {STICKERS.map((sticker) => <button className="sticker-button" key={sticker} onClick={() => addSticker(sticker)} type="button">{sticker}</button>)}
        <input aria-label="커스텀 이모지" maxLength={12} onChange={(event) => setCustomEmoji(event.target.value)} placeholder="커스텀 이모지" value={customEmoji} />
        <button className="tool-button" disabled={!customEmoji.trim() || Array.from(customEmoji.trim()).length > 12} onClick={addCustomEmoji} type="button">이모지 추가</button>
        <input aria-label="텍스트 레이어" maxLength={40} onChange={(event) => setTextValue(event.target.value)} placeholder="텍스트" value={textValue} />
        <button className="tool-button" disabled={!textValue.trim()} onClick={addText} type="button">텍스트 추가</button>
        <label className="file-layer-button">
          {uploadingLayer ? "업로드 중…" : "사진 삽입"}
          <input accept="image/jpeg,image/png,image/webp" disabled={uploadingLayer} onChange={(event) => { const file = event.target.files?.[0]; if (file) void addImageFromFile(file); event.target.value = ""; }} type="file" />
        </label>
      </div>
      {layerError && <p className="inline-message auth-error">{layerError}</p>}
      {draftError && <p className="inline-message auth-error">{draftError}</p>}
      {selectedLayer && (
        <div className="layer-controls">
          <label>크기 <input max="0.3" min="0.03" onChange={(event) => updateSelected({ scale: Number(event.target.value) })} step="0.005" type="range" value={selectedLayer.scale} /></label>
          <label>회전 <input max="180" min="-180" onChange={(event) => updateSelected({ rotation: Number(event.target.value) })} step="1" type="range" value={selectedLayer.rotation} /></label>
          <button className="tool-button danger-button" onClick={deleteSelected} type="button">삭제</button>
        </div>
      )}
      <div className="adjustment-controls">
        <button className="tool-button" onClick={() => setRotation((value) => (value + 90) % 360)} type="button">⟳ 90° 회전</button>
        <button className={cropSquare ? "tool-button active" : "tool-button"} onClick={() => setCropSquare((value) => !value)} type="button">□ 정사각형 자르기</button>
        <label>밝기 <input max="150" min="50" onChange={(event) => setBrightness(Number(event.target.value))} step="1" type="range" value={brightness} /></label>
        <output>{brightness}%</output>
      </div>
      <div className="canvas-stage">
        {imageState === "loading" && <p className="canvas-message">사진을 준비하고 있어요…</p>}
        {imageState === "error" && <p className="canvas-message error">사진을 불러오지 못했어요.</p>}
        <canvas aria-label="편집 대상 사진" className={imageState === "ready" ? "editor-canvas visible" : "editor-canvas"} onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={finishPointer} onPointerCancel={finishPointer} ref={canvasRef} />
      </div>
      <label className="zoom-control" htmlFor="editor-zoom"><span>확대/축소</span><input id="editor-zoom" max="2" min="0.75" onChange={(event) => setZoom(Number(event.target.value))} step="0.05" type="range" value={zoom} /><output>{Math.round(zoom * 100)}%</output></label>
      <div className="draft-controls">
        <button className="tool-button active" disabled={draftState === "saving" || draftState === "loading" || imageState !== "ready" || submissionState === "submitted"} onClick={() => void saveCurrentDraft()} type="button">
          {draftState === "saving" ? "초안 저장 중…" : "초안 저장"}
        </button>
        <button className="tool-button" disabled={draftState === "saving" || draftState === "loading" || submissionState === "submitted"} onClick={() => void removeDraft()} type="button">초안 취소</button>
        <button className="tool-button active" disabled={draftState === "saving" || draftState === "loading" || imageState !== "ready" || submissionState === "submitted"} onClick={() => void submitCurrentDraft()} type="button">
          {submissionState === "submitting" ? "제출 중…" : submissionState === "submitted" ? "제출 완료" : "완료하고 보내기"}
        </button>
        <span className="draft-status">{submissionState === "submitted" ? "상대가 완료할 때까지 결과는 비공개입니다." : draftState === "saved" ? `저장됨 · v${draftVersion}` : draftState === "dirty" ? "저장되지 않은 변경" : draftState === "loading" ? "초안 확인 중…" : "임시 초안 없음"}</span>
      </div>
      <p className="editor-note">레이어를 선택해 이동·크기·회전을 조정하고, 필요하면 삭제할 수 있습니다.</p>
    </section>
  );
}
