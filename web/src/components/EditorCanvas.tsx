import { useEffect, useRef, useState } from "react";
import { getAssetUrl, type InboxItem } from "../api";

interface EditorCanvasProps {
  item: InboxItem;
}

export function EditorCanvas({ item }: EditorCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [zoom, setZoom] = useState(1);
  const [imageState, setImageState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const maxWidth = 960;
      const maxHeight = 640;
      const fitScale = Math.min(maxWidth / image.naturalWidth, maxHeight / image.naturalHeight, 1);
      const width = Math.max(1, Math.round(image.naturalWidth * fitScale * zoom));
      const height = Math.max(1, Math.round(image.naturalHeight * fitScale * zoom));
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) return;
      context.clearRect(0, 0, width, height);
      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      context.drawImage(image, 0, 0, width, height);
      setImageState("ready");
    };
    image.onerror = () => setImageState("error");
    image.src = getAssetUrl(item.input.url);
  }, [item, zoom]);

  return (
    <section className="editor-panel" aria-label="사진 편집 캔버스">
      <div className="editor-heading">
        <div>
          <p className="eyebrow">EDITOR PREVIEW</p>
          <h3>편집할 사진</h3>
        </div>
        <span className="editor-size">{item.input.width} × {item.input.height}</span>
      </div>
      <div className="canvas-stage">
        {imageState === "loading" && <p className="canvas-message">사진을 준비하고 있어요…</p>}
        {imageState === "error" && <p className="canvas-message error">사진을 불러오지 못했어요.</p>}
        <canvas
          aria-label="편집 대상 사진"
          className={imageState === "ready" ? "editor-canvas visible" : "editor-canvas"}
          ref={canvasRef}
        />
      </div>
      <label className="zoom-control" htmlFor="editor-zoom">
        <span>확대/축소</span>
        <input
          id="editor-zoom"
          max="2"
          min="0.75"
          onChange={(event) => setZoom(Number(event.target.value))}
          step="0.05"
          type="range"
          value={zoom}
        />
        <output>{Math.round(zoom * 100)}%</output>
      </label>
      <p className="editor-note">이 화면은 편집 대상 확인 단계입니다. 그리기와 레이어 도구는 다음 단계에서 추가됩니다.</p>
    </section>
  );
}
