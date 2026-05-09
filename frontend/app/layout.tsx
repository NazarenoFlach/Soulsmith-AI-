import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "SoulSmith AI",
  description: "Dark Souls 1 build generator"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  );
}
