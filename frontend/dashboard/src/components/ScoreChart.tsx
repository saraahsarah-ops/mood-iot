"use client";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface ScoreChartProps {
  data: Record<string, string | number>[];
  patients?: string[];
  height?: number;
}

const COLORS = ["#0288d1", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12"];

export default function ScoreChart({ data, patients, height = 300 }: ScoreChartProps) {
  // Si plusieurs patients, grouper par date
  if (patients && patients.length > 1) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="date" fontSize={12} />
          <YAxis domain={[0, 100]} fontSize={12} />
          <Tooltip />
          <Legend />
          <ReferenceLine y={40} stroke="#f39c12" strokeDasharray="5 5" label="Niveau 2" />
          <ReferenceLine y={70} stroke="#e74c3c" strokeDasharray="5 5" label="Niveau 3" />
          {patients.map((p, i) => (
            <Line
              key={p}
              type="monotone"
              dataKey={p}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="date" fontSize={12} />
        <YAxis domain={[0, 100]} fontSize={12} />
        <Tooltip />
        <ReferenceLine y={40} stroke="#f39c12" strokeDasharray="5 5" label="Niveau 2" />
        <ReferenceLine y={70} stroke="#e74c3c" strokeDasharray="5 5" label="Niveau 3" />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#0288d1"
          strokeWidth={2}
          dot={{ r: 3 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
