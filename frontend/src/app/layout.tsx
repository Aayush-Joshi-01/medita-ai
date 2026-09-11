import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "medita-ai",
  description: "AI-assisted telemedicine and clinical support platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
