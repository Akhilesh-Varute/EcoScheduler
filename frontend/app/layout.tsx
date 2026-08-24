import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "EcoScheduler",
  description: "AWS EC2 cost-optimization scheduler",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
