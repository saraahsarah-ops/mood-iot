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
  Area,
  AreaChart,
} from "recharts";

interface ScoreChartProps {
  data: Record<string, string | number>[];
  patients?: string[];
  height?: number;
}

const COLORS = ["#0288d1", "#e74c3c", "#2ecc71", "#9b59b6", "#f39c12"];

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload) return null;
  return (
    <div className="rounded-xl border border-gray-100 bg-white px-4 py-3 shadow-lg">
      <p className="text-xs font-semibold text-gray-500">{label}</p>
      <div className="mt-1 space-y-1">
        {payload.map((item: any, i: number) => (
          <div key={i} className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: item.color }} />
            <span className="text-xs text-gray-600">{item.name}:</span>
            <span className="text-xs font-bold text-gray-800">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default function ScoreChart({ data, patients, height = 300 }: ScoreChartProps) {
  if (patients && patients.length > 1) {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data}>
          <defs>
            {patients.map((_, i) => (
              <linearGradient key={i} id={`lineGrad${i}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.3} />
                <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0} />
              </linearGradient>
            ))}
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis
            dataKey="date"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: "#e2e8f0" }}
            tick={{ fill: "#94a3b8" }}
          />
          <YAxis
            domain={[0, 100]}
            fontSize={11}
            tickLine={false}
            axisLine={false}
            tick={{ fill: "#94a3b8" }}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: "12px", paddingTop: "12px" }}
            iconType="circle"
            iconSize={8}
          />
          <ReferenceLine y={40} stroke="#f59e0b" strokeDasharray="6 4" strokeWidth={1} />
          <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="6 4" strokeWidth={1} />
          {patients.map((p, i) => (
            <Line
              key={p}
              type="monotone"
              dataKey={p}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2.5}
              dot={false}
              activeDot={{ r: 4, strokeWidth: 2, fill: "#fff" }}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data}>
        <defs>
          <linearGradient id="scoreGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#0288d1" stopOpacity={0.15} />
            <stop offset="100%" stopColor="#0288d1" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="date"
          fontSize={11}
          tickLine={false}
          axisLine={{ stroke: "#e2e8f0" }}
          tick={{ fill: "#94a3b8" }}
        />
        <YAxis
          domain={[0, 100]}
          fontSize={11}
          tickLine={false}
          axisLine={false}
          tick={{ fill: "#94a3b8" }}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={40} stroke="#f59e0b" strokeDasharray="6 4" strokeWidth={1} />
        <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="6 4" strokeWidth={1} />
        <Area
          type="monotone"
          dataKey="score"
          stroke="#0288d1"
          strokeWidth={2.5}
          fill="url(#scoreGradient)"
          dot={{ r: 3, fill: "#0288d1", strokeWidth: 0 }}
          activeDot={{ r: 5, strokeWidth: 2, fill: "#fff", stroke: "#0288d1" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
