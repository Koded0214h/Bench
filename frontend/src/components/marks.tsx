// Bench marks — ported from the launch film.
// BenchMark: the 12-spoke radial burst (the primary identity).
// PixelCritter: a blocky worker glyph, same vibe as the Claude pixel icon.

type MarkProps = {
  size?: number;
  color?: string;
  className?: string;
  title?: string;
};

export function BenchMark({ size = 24, color = "var(--teal)", className, title }: MarkProps) {
  const N = 12;
  const spokes = [];
  for (let i = 0; i < N; i++) {
    const long = i % 2 === 0;
    const len = long ? 46 : 30;
    const w = long ? 5 : 3.8;
    const a = (i * 360) / N;
    const d =
      `M0 0 C ${w} ${-len * 0.42}, ${w} ${-len * 0.78}, 0 ${-len} ` +
      `C ${-w} ${-len * 0.78}, ${-w} ${-len * 0.42}, 0 0 Z`;
    spokes.push(<path key={i} transform={`rotate(${a})`} d={d} />);
  }
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="-58 -58 116 116"
      fill={color}
      role={title ? "img" : "presentation"}
      aria-hidden={title ? undefined : true}
    >
      {title ? <title>{title}</title> : null}
      {spokes}
    </svg>
  );
}

// 7x7 grid, "#" = filled cell. Two eye gaps, antenna + feet nubs.
const CRITTER = [
  ".#...#.",
  "#######",
  "#.###.#",
  "#######",
  "#######",
  "##.#.##",
  ".#...#.",
];

export function PixelCritter({ size = 20, color = "var(--teal)", className }: MarkProps) {
  const cell = 100 / 7;
  const rects = CRITTER.flatMap((row, y) =>
    [...row].map((c, x) =>
      c === "#" ? (
        <rect
          key={`${x}-${y}`}
          x={x * cell}
          y={y * cell}
          width={cell + 0.4}
          height={cell + 0.4}
        />
      ) : null,
    ),
  );
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill={color}
      aria-hidden="true"
      shapeRendering="crispEdges"
    >
      {rects}
    </svg>
  );
}
