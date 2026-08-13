// DS Section 2: the single canonical source for every version of the
// Teenure mark and wordmark. No other file should construct or
// approximate the logo from scratch -- grep for raw "teen"/"ure" SVG
// text or hex-coded hexagon paths outside this file is a violation.

const TEAL = "#0D9B7A";

function frameColor(darkMode: boolean) {
  return darkMode ? "#FFFFFF" : "#0F1929";
}

/** The hexagonal badge with a T letterform. Nav sidebars, favicon, small contexts. */
export function LogoMark({ size = 40, darkMode = false }: { size?: number; darkMode?: boolean }) {
  const frame = frameColor(darkMode);
  return (
    <svg viewBox="0 0 80 80" width={size} height={size} xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <polygon
        points="68,40 54,64.25 26,64.25 12,40 26,15.75 54,15.75"
        fill="none"
        stroke={frame}
        strokeWidth="2.5"
        strokeLinejoin="miter"
      />
      <path d="M 21,27 H 59 V 34 H 43 V 59 H 37 V 34 H 21 Z" fill={TEAL} />
      <circle cx="21" cy="30.5" r="3.5" fill={TEAL} />
      <circle cx="59" cy="30.5" r="3.5" fill={TEAL} />
    </svg>
  );
}

/** Horizontal mark + wordmark lockup. Marketing site nav, auth page header. */
export function LogoWordmark({ darkMode = false, height = 30 }: { darkMode?: boolean; height?: number }) {
  const frame = frameColor(darkMode);
  const ink = frame;
  return (
    <svg
      viewBox="0 0 300 76"
      height={height}
      width={Math.round(height * (300 / 76))}
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Teenure"
      role="img"
    >
      <polygon
        points="110,38 100,55.32 80,55.32 70,38 80,20.68 100,20.68"
        fill="none"
        stroke={frame}
        strokeWidth="2.5"
        strokeLinejoin="miter"
      />
      <path d="M 76,29 H 104 V 34 H 92 V 52 H 88 V 34 H 76 Z" fill={TEAL} />
      <circle cx="76" cy="31.5" r="2.5" fill={TEAL} />
      <circle cx="104" cy="31.5" r="2.5" fill={TEAL} />
      <text
        x="122"
        y="45"
        textAnchor="start"
        fontFamily="Inter, 'Helvetica Neue', Arial, sans-serif"
        fontSize="28"
        fontWeight="700"
        style={{ letterSpacing: "-0.5px" }}
      >
        <tspan fill={ink}>teen</tspan>
        <tspan fill={TEAL}>ure</tspan>
      </text>
    </svg>
  );
}

/** Mark above wordmark. Marketing hero, the /verified/:token public profile. */
export function LogoStacked({ darkMode = false, width = 220 }: { darkMode?: boolean; width?: number }) {
  const frame = frameColor(darkMode);
  const ink = frame;
  return (
    <svg
      viewBox="0 0 300 140"
      width={width}
      height={Math.round(width * (140 / 300))}
      xmlns="http://www.w3.org/2000/svg"
      aria-label="Teenure"
      role="img"
    >
      <polygon
        points="178,46 164,70.25 136,70.25 122,46 136,21.75 164,21.75"
        fill="none"
        stroke={frame}
        strokeWidth="3"
        strokeLinejoin="miter"
      />
      <path d="M 131,33 H 169 V 40 H 153 V 65 H 147 V 40 H 131 Z" fill={TEAL} />
      <circle cx="131" cy="36.5" r="3.5" fill={TEAL} />
      <circle cx="169" cy="36.5" r="3.5" fill={TEAL} />
      <text
        x="150"
        y="104"
        textAnchor="middle"
        fontFamily="Inter, 'Helvetica Neue', Arial, sans-serif"
        fontSize="34"
        fontWeight="700"
        style={{ letterSpacing: "-0.6px" }}
      >
        <tspan fill={ink}>teen</tspan>
        <tspan fill={TEAL}>ure</tspan>
      </text>
      <text
        x="150"
        y="122"
        textAnchor="middle"
        fontFamily="Inter, 'Helvetica Neue', Arial, sans-serif"
        fontSize="11.5"
        fontWeight="400"
        fill={ink}
        fillOpacity={darkMode ? "0.32" : "0.38"}
        style={{ letterSpacing: "0.15px" }}
      >
        Earn yours early.
      </text>
    </svg>
  );
}
