import React, { useEffect, useRef, useState, useCallback } from "react";
import mermaid from "mermaid";
import DOMPurify from "dompurify";
import type { ArchitectureComponent } from "../../api";

interface MermaidDiagramProps {
  chart: string;
  components?: ArchitectureComponent[];
  selectedComponentId?: string | null;
  onSelectComponent?: (componentId: string) => void;
  className?: string;
  githubUrl?: string;
}

let mermaidInitialized = false;

function initMermaid(isDark: boolean) {
  try {
    mermaid.initialize({
      startOnLoad: false,
      suppressErrorRendering: true,
      securityLevel: "loose",
      theme: "base",
      themeVariables: isDark
        ? {
            background: "#13171f",
            primaryColor: "#1e2634",
            primaryBorderColor: "#3b82f6",
            primaryTextColor: "#f1f5f9",
            lineColor: "#f59e0b",
            secondaryColor: "#1a2230",
            tertiaryColor: "#242f42",
            mainBkg: "#18202c",
            nodeBorder: "#3b82f6",
            clusterBkg: "rgba(30, 41, 59, 0.45)",
            clusterBorder: "#475569",
            titleColor: "#e2e8f0",
            edgeLabelBackground: "#1e293b",
          }
        : {
            background: "#ffffff",
            primaryColor: "#f1f5f9",
            primaryBorderColor: "#2563eb",
            primaryTextColor: "#0f172a",
            lineColor: "#d97706",
            secondaryColor: "#f8fafc",
            tertiaryColor: "#e2e8f0",
            mainBkg: "#ffffff",
            nodeBorder: "#2563eb",
            clusterBkg: "rgba(241, 245, 249, 0.65)",
            clusterBorder: "#cbd5e1",
            titleColor: "#1e293b",
            edgeLabelBackground: "#ffffff",
          },
      flowchart: {
        wrappingWidth: 220,
        curve: "basis",
        nodeSpacing: 50,
        rankSpacing: 65,
        padding: 16,
        htmlLabels: true,
      },
    });
    mermaidInitialized = true;
  } catch (err) {
    console.error("Mermaid initialization error:", err);
  }
}

export function MermaidDiagram({
  chart,
  components = [],
  selectedComponentId,
  onSelectComponent,
  className = "",
  githubUrl,
}: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [renderError, setRenderError] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"diagram" | "code">("diagram");
  const [copied, setCopied] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Pan & Zoom state
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [transitionEnabled, setTransitionEnabled] = useState(false);
  const isDragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });

  // Detect dark theme
  const isDark =
    typeof document !== "undefined" &&
    document.documentElement.getAttribute("data-theme") === "dark";

  // Re-render chart whenever code or theme changes
  useEffect(() => {
    let isCancelled = false;
    if (!chart || !chart.trim()) return;

    initMermaid(isDark);

    const renderId = `mermaid-svg-${Math.random().toString(36).substring(2, 9)}`;

    mermaid
      .render(renderId, chart)
      .then(({ svg }) => {
        if (!isCancelled) {
          const sanitized = DOMPurify.sanitize(svg, {
            USE_PROFILES: { svg: true, svgFilters: true },
            ADD_TAGS: ["foreignObject"],
            ADD_ATTR: ["target", "onclick"],
          });
          setSvgContent(sanitized);
          setRenderError(null);
        }
      })
      .catch((err) => {
        if (!isCancelled) {
          console.warn("Mermaid render warning, attempting fallback render:", err);
          setRenderError(err.message || "Failed to render diagram.");
        }
      });

    return () => {
      isCancelled = true;
    };
  }, [chart, isDark]);

  // Bind interactive click handlers to rendered SVG nodes
  useEffect(() => {
    if (!containerRef.current || !svgContent) return;

    const svgElement = containerRef.current.querySelector("svg");
    if (!svgElement) return;

    // Enhance SVG attributes for responsive sizing
    svgElement.setAttribute("width", "100%");
    svgElement.setAttribute("height", "100%");
    svgElement.style.maxWidth = "100%";
    svgElement.style.height = "auto";
    svgElement.style.overflow = "visible";

    // Find all node elements in the SVG
    const nodes = svgElement.querySelectorAll(".node");
    nodes.forEach((nodeEl) => {
      const el = nodeEl as HTMLElement;
      el.style.cursor = "pointer";

      const id = el.id || "";
      const rawId = id.replace(/^node_/, "").replace(/_[0-9]+$/, "");

      // Check if this node corresponds to a component
      const matchedComp = components.find(
        (c) =>
          c.id === rawId ||
          id.includes(c.id) ||
          el.textContent?.toLowerCase().includes(c.name.toLowerCase())
      );

      if (matchedComp && matchedComp.id === selectedComponentId) {
        el.classList.add("selected-mermaid-node");
      } else {
        el.classList.remove("selected-mermaid-node");
      }

      el.onclick = (e) => {
        e.stopPropagation();
        if (matchedComp && onSelectComponent) {
          onSelectComponent(matchedComp.id);
        } else if (rawId && onSelectComponent) {
          onSelectComponent(rawId);
        }
      };
    });
  }, [svgContent, components, selectedComponentId, onSelectComponent]);

  // Zoom and Pan Handlers - Tuned for responsive, smooth, natural navigation
  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    setTransitionEnabled(false);

    // Normalize delta across input devices:
    // e.deltaMode 1: lines (standard mouse wheel), e.deltaMode 0: pixels (trackpad / high-res)
    const isPinch = e.ctrlKey;
    const rawDelta = e.deltaMode === 1 ? e.deltaY * 20 : e.deltaY;
    const zoomSensitivity = isPinch ? 0.008 : 0.0022;
    const delta = -rawDelta * zoomSensitivity;

    // Responsive clamp: prevents runaway zoom without feeling sticky or sluggish
    const clampedDelta = Math.max(-0.075, Math.min(0.075, delta));

    setZoom((prevZoom) => {
      const nextZoom = Math.min(Math.max(0.3, prevZoom * (1 + clampedDelta)), 3.5);
      const roundedZoom = Number(nextZoom.toFixed(4));

      // Anchor zoom around cursor position so diagram doesn't drift away
      if (viewportRef.current) {
        const rect = viewportRef.current.getBoundingClientRect();
        const cursorX = e.clientX - (rect.left + rect.width / 2);
        const cursorY = e.clientY - (rect.top + rect.height / 2);
        const scaleRatio = roundedZoom / prevZoom;

        setPan((prevPan) => ({
          x: Math.round(prevPan.x - cursorX * (scaleRatio - 1)),
          y: Math.round(prevPan.y - cursorY * (scaleRatio - 1)),
        }));
      }

      return roundedZoom;
    });
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return; // only left click
    setTransitionEnabled(false);
    isDragging.current = true;
    dragStart.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current) return;
    setPan({
      x: e.clientX - dragStart.current.x,
      y: e.clientY - dragStart.current.y,
    });
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  const handleZoomIn = () => {
    setTransitionEnabled(true);
    setZoom((prev) => Math.min(Number((prev + 0.18).toFixed(2)), 3.5));
  };
  const handleZoomOut = () => {
    setTransitionEnabled(true);
    setZoom((prev) => Math.max(Number((prev - 0.18).toFixed(2)), 0.3));
  };
  const handleResetZoom = () => {
    setTransitionEnabled(true);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleCopyCode = () => {
    navigator.clipboard.writeText(chart);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSvg = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `system-architecture-${Date.now()}.svg`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const toggleFullscreen = () => {
    setIsFullscreen((prev) => !prev);
  };

  return (
    <div
      className={`gitdiagram-container ${isFullscreen ? "fullscreen" : ""} ${className}`}
    >
      {/* Interactive Top Toolbar */}
      <div className="gitdiagram-toolbar">
        <div className="gitdiagram-view-toggle">
          <button
            type="button"
            className={`gitdiagram-btn ${viewMode === "diagram" ? "active" : ""}`}
            onClick={() => setViewMode("diagram")}
            title="Interactive Diagram View"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7"></rect>
              <rect x="14" y="3" width="7" height="7"></rect>
              <rect x="14" y="14" width="7" height="7"></rect>
              <rect x="3" y="14" width="7" height="7"></rect>
            </svg>
            <span>Diagram</span>
          </button>
          <button
            type="button"
            className={`gitdiagram-btn ${viewMode === "code" ? "active" : ""}`}
            onClick={() => setViewMode("code")}
            title="Mermaid Source Code"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="16 18 22 12 16 6"></polyline>
              <polyline points="8 6 2 12 8 18"></polyline>
            </svg>
            <span>Mermaid Code</span>
          </button>
        </div>

        {/* Viewport & Export Controls */}
        <div className="gitdiagram-actions">
          {viewMode === "diagram" && (
            <div className="gitdiagram-zoom-group">
              <button
                type="button"
                className="gitdiagram-icon-btn"
                onClick={handleZoomOut}
                title="Zoom Out (-)"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
              <button
                type="button"
                className="gitdiagram-zoom-badge"
                onClick={handleResetZoom}
                title="Reset Zoom (100%)"
              >
                {Math.round(zoom * 100)}%
              </button>
              <button
                type="button"
                className="gitdiagram-icon-btn"
                onClick={handleZoomIn}
                title="Zoom In (+)"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19"></line>
                  <line x1="5" y1="12" x2="19" y2="12"></line>
                </svg>
              </button>
              <button
                type="button"
                className="gitdiagram-icon-btn"
                onClick={handleResetZoom}
                title="Fit to Screen"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path>
                </svg>
              </button>
            </div>
          )}

          <button
            type="button"
            className="gitdiagram-icon-btn"
            onClick={handleCopyCode}
            title={copied ? "Copied!" : "Copy Mermaid Code"}
          >
            {copied ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#22c55e" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
              </svg>
            )}
          </button>

          <button
            type="button"
            className="gitdiagram-icon-btn"
            onClick={handleDownloadSvg}
            title="Download SVG Diagram"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
          </button>

          <button
            type="button"
            className="gitdiagram-icon-btn"
            onClick={toggleFullscreen}
            title={isFullscreen ? "Exit Fullscreen" : "Fullscreen View"}
          >
            {isFullscreen ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 14 10 14 10 20"></polyline>
                <polyline points="20 10 14 10 14 4"></polyline>
                <line x1="14" y1="10" x2="21" y2="3"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="15 3 21 3 21 9"></polyline>
                <polyline points="9 21 3 21 3 15"></polyline>
                <line x1="21" y1="3" x2="14" y2="10"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Main Canvas Area */}
      {viewMode === "diagram" ? (
        <div
          ref={viewportRef}
          className="gitdiagram-viewport"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {renderError ? (
            <div className="gitdiagram-error-box">
              <p className="gitdiagram-error-title">Diagram Parsing Notice</p>
              <p className="gitdiagram-error-desc">{renderError}</p>
              <button
                type="button"
                className="btn btn-sm btn-secondary"
                onClick={() => setViewMode("code")}
              >
                Inspect Mermaid Code
              </button>
            </div>
          ) : (
            <div
              ref={containerRef}
              className="gitdiagram-svg-stage"
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                transformOrigin: "center center",
                transition: transitionEnabled ? "transform 0.22s cubic-bezier(0.16, 1, 0.3, 1)" : "none",
              }}
              dangerouslySetInnerHTML={{ __html: svgContent }}
            />
          )}

          {/* Canvas Bottom Hint */}
          <div className="gitdiagram-hint-pill">
            <span>💡 Click any node to inspect subsystem details & code files • Drag to pan • Scroll to zoom</span>
          </div>
        </div>
      ) : (
        <div className="gitdiagram-code-view">
          <pre className="gitdiagram-code-block">
            <code>{chart}</code>
          </pre>
        </div>
      )}
    </div>
  );
}
