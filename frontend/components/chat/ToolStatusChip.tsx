export function ToolStatusChip({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 text-xs text-gray-500 py-1 px-1">
      <svg
        className="animate-spin h-3 w-3 text-indigo-500 flex-shrink-0"
        xmlns="http://www.w3.org/2000/svg"
        fill="none"
        viewBox="0 0 24 24"
      >
        <circle
          className="opacity-25"
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="4"
        />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
        />
      </svg>
      <span>{label}</span>
    </div>
  );
}
