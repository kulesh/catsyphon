/**
 * Sparkline component - renders a small inline chart for time-series data.
 * Supports both line and bar chart modes.
 */

interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
  strokeWidth?: number;
  fillOpacity?: number;
  variant?: 'line' | 'bar';
  barGap?: number;
}

export function Sparkline({
  data,
  width = 100,
  height = 30,
  color = 'currentColor',
  strokeWidth = 2,
  fillOpacity = 0.1,
  variant = 'line',
  barGap = 1,
}: SparklineProps) {
  if (!data || data.length === 0) {
    return null;
  }

  // Calculate min/max for scaling
  const validData = data.filter((d) => d !== null && !isNaN(d));
  if (validData.length === 0) {
    return null;
  }

  const max = Math.max(...validData);
  const scaleMax = max || 1; // Avoid division by zero

  if (variant === 'bar') {
    // Bar chart rendering
    const barWidth = (width - (data.length - 1) * barGap) / data.length;

    return (
      <svg
        width={width}
        height={height}
        className="inline-block"
        style={{ verticalAlign: 'middle' }}
      >
        {data.map((value, index) => {
          const barHeight = (value / scaleMax) * height;
          const x = index * (barWidth + barGap);
          const y = height - barHeight;

          return (
            <rect
              key={index}
              x={x}
              y={y}
              width={barWidth}
              height={barHeight}
              fill={color}
              fillOpacity={value > 0 ? 0.7 : 0.2}
              rx={1}
            />
          );
        })}
      </svg>
    );
  }

  // Line chart rendering (original behavior)
  const min = Math.min(...validData);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - min) / range) * height;
    return `${x},${y}`;
  });

  const linePath = `M ${points.join(' L ')}`;
  const areaPath = `${linePath} L ${width},${height} L 0,${height} Z`;

  return (
    <svg
      width={width}
      height={height}
      className="inline-block"
      style={{ verticalAlign: 'middle' }}
    >
      {/* Fill area under the line */}
      <path
        d={areaPath}
        fill={color}
        fillOpacity={fillOpacity}
        stroke="none"
      />
      {/* Line */}
      <path
        d={linePath}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
