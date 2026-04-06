// app/layout.tsx — Root layout
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "react-hot-toast";
import { Navbar } from "@/components/layout/Navbar";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title:       "CyberRAG IDS — Local LLM Cyber Advisor",
  description: "Real-time network intrusion detection with RAG-powered cybersecurity advisor",
  keywords:    ["cybersecurity", "IDS", "LSTM", "RAG", "LLM", "network security"],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} min-h-screen bg-slate-950`}>
        <Navbar />
        <main className="mx-auto max-w-screen-xl px-4 py-6">
          {children}
        </main>
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: "#0f172a",
              color:      "#e2e8f0",
              border:     "1px solid #1e293b",
              fontSize:   "13px",
            },
            success: { iconTheme: { primary: "#34d399", secondary: "#0f172a" } },
            error:   { iconTheme: { primary: "#f87171", secondary: "#0f172a" } },
          }}
        />
      </body>
    </html>
  );
}
