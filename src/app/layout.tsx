import "./globals.css";

export const metadata = {
  title: "HPO Normalizer + PubCaseFinder Demo",
  description: "日本語テキストから症状抽出→HPO正規化→PubCaseFinderで疾患予測"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="min-h-screen bg-[radial-gradient(1200px_800px_at_20%_10%,#13214a_0%,#0b1020_60%)] font-sans text-slate-100">
        {children}
      </body>
    </html>
  );
}
