import type { ReactNode } from "react";

export function PageLede({ titulo, children }: { titulo: string; children?: ReactNode }) {
  return (
    <div className="page-lede">
      <h2 style={{ fontSize: 20 }}>{titulo}</h2>
      {children && <p>{children}</p>}
    </div>
  );
}
