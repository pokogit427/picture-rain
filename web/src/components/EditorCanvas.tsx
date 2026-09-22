import { useEffect, useRef, useState } from "react";
import { getAssetUrl, type InboxItem } from "../api";

type Point = { x: number; y: number };
type Stroke = { points: Point[]; color: string; width: number };
type ToolMode = "brush" | "eraser";

interface EditorCanvasProps {
  item: InboxItem;
}

const BRUSH_COLOR = "#ffde8a";

function drawScene(
  canvas: HTMLCanvasElement,
  image: HTMLImageElement,
  zoom: number,
  strokes: Stroke[],
  activeStroke: Stroke | null,
) {
  const maxWidth = 960;
  const maxHeight = 640;
  const fitScale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight, 1);
  const width = Math.max(1, Math.round(image.naturalWidth * fitScale * zoom));
  const height = Math.max(1, Math.round(image.naturalHeight * fitScale * zoom));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d");
  if (!context) return;
  context.clearRect(0, 0, width, height);
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  context.drawImage(image, 0, 0, width, height);
  for (const stroke of activeStroke ? [...strokes, activeStroke] : strokes) {
    if (stroke.points.length < 2) continue;
    context.beginPath();
    context.moveTo(stroke.points[0].x * width, stroke.points[0].y * height);
    for (const point of stroke.points.slice(1)) {
      context.lineTo(point.x * width, point.y * height);
    }
    context.strokeStyle = stroke.color;
    context.lineWidth = stroke.width * Math.min(width, height);
    context.lineCap = "round";
    context.lineJoin = "round";
    context.stroke();
  }
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

export function EditorCanvas({ item }: EditorCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const [zoom, setZoom] = useState(1);
  const [imageState, setImageState] = useState<"loading" | "ready" | "error">("loading");
  const [mode, setMode] = useState<ToolMode>("brush");
  const [past, setPast] = useState<Stroke[][]>([]);
  const [present, setPresent] = useState<Stroke[]>([]);
  const [future, setFuture] = useState<Stroke[][]>([]);
  const [activeStroke, setActiveStroke] = useState<Stroke | null>(null);
  const eraseBaseRef = useRef<Stroke[] | null>(null);

  useEffect(() => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      imageRef.current = image;
      setPresent([]);
      setPast([]);
      setFuture([]);
      setImageState("ready");
    };
    image.onerror = () => setImageState("error");
    image.src = getAssetUrl(item.input.url);
  }, [item]);

  useEffect(() => {
    if (imageRef.current && canvasRef.current) {
      drawScene(canvasRef.current, imageRef.current, zoom, present, activeStroke);
    }
  }, [zoom, present, activeStroke]);

  function pointFromEvent(event: React.PointerEvent<HTMLCanvasElement>): Point {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const bounds = canvas.getBoundingClientRect();
    return {
      x: Math.min(1, Math.max(0, (event.clientX - bounds.left) / bounds.width)),
      y: Math.min(1, Math.max(0, (event.clientY - bounds.top) / bounds.height)),
    };
  }

  function handlePointerDown(event: React.PointerEvent<HTMLCanvasElement>) {
    if (imageState !== "ready") return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = pointFromEvent(event);
    if (mode === "eraser") {
      eraseBaseRef.current = present;
      return;
    }
    setFuture([]);
    setActiveStroke({ points: [point], color: BRUSH_COLOR, width: 0.012 });
  }

  function handlePointerMove(event: React.PointerEvent<HTMLCanvasElement>) {
    const point = pointFromEvent(event);
    if (mode === "eraser") {
      if (!eraseBaseRef.current) return;
      setPresent((current) => {
        const filtered = current.filter((stroke) => !stroke.points.some((candidate) => distance(candidate, point) < 0.045));
        if (filtered.length !== current.length && eraseBaseRef.current === current) {
          setPast((history) => [...history, current]);
          eraseBaseRef.current = filtered;
        }
        return filtered;
      });
      return;
    }
    setActiveStroke((current) => current ? { ...current, points: [...current.points, point] } : current);
  }

  function finishPointer(event: React.PointerEvent<HTMLCanvasElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (mode === "eraser") {
      eraseBaseRef.current = null;
      return;
    }
    setActiveStroke((stroke) => {
      if (!stroke || stroke.points.length < 2) return null;
      setPast((history) => [...history, present]);
      return null;
    });
  }

  function undo() {
    if (past.length === 0) return;
    const previous = past[past.length - 1];
    setFuture((history) => [present, ...history]);
    setPresent(previous);
    setPast(past.slice(0, -1));
  }

  function redo() {
    if (future.length === 0) return;
    const next = future[0];
    setPast((history) => [...history, present]);
    setPresent(next);
    setFuture(future.slice(1));
  }

  return (
    <section className="editor-panel" aria-label="사진 편집 캔버스">
      <div className="editor-heading">
        <div>
          <p className="eyebrow">EDITOR PREVIEW</p>
          <h3>편집할 사진</h3>
        </div>
        <span className="editor-size">{item.input.width} × {item.input.height}</span>
      </div>
      <div className="editor-toolbar" aria-label="그리기 도구">
        <button className={mode === "brush" ? "tool-button active" : "tool-button"} onClick={() => setMode("brush")} type="button">✎ 그리기</button>
        <button className={mode === "eraser" ? "tool-button active" : "tool-button"} onClick={() => setMode("eraser")} type="button">⌫ 선 지우기</button>
        <span className="tool-spacer" />
        <button className="tool-button" disabled={past.length === 0} onClick={undo} type="button">↶</button>
        <button className="tool-button" disabled={future.length === 0} onClick={redo} type="button">↷</button>
      </div>
      <div className="canvas-stage">
        {imageState === "loading" && <p className="canvas-message">사진을 준비하고 있어요…</p>}
        {imageState === "error" && <p className="canvas-message error">사진을 불러오지 못했어요.</p>}
        <canvas
          aria-label="편집 대상 사진"
          className={imageState === "ready" ? "editor-canvas visible" : "editor-canvas"}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={finishPointer}
          onPointerCancel={finishPointer}
          ref={canvasRef}
        />
      </div>
      <label className="zoom-control" htmlFor="editor-zoom">
        <span>확대/축소</span>
        <input id="editor-zoom" max="2" min="0.75" onChange={(event) => setZoom(Number(event.target.value))} step="0.05" type="range" value={zoom} />
        <output>{Math.round(zoom * 100)}%</output>
      </label>
      <p className="editor-note">선은 사진 위 레이어로 관리되며 실행 취소·다시 실행과 자기 선 지우기를 지원합니다.</p>
    </section>
  );
}
