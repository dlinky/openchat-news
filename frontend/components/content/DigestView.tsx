"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
  title: string;
  subtitle?: string;
  content: string;
}

export function DigestView({ title, subtitle, content }: Props) {
  return (
    <article className="max-w-2xl mx-auto px-4 py-8 lg:py-12">
      {/* 헤더 */}
      <header className="mb-8 pb-6 border-b border-neutral-100">
        <p className="text-xs font-semibold text-orange-500 uppercase tracking-widest mb-2">
          ChatDigest
        </p>
        <h1 className="text-2xl lg:text-3xl font-bold text-neutral-900">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-neutral-400">{subtitle}</p>}
      </header>

      {/* 콘텐츠 */}
      <div className="prose prose-neutral max-w-none
        prose-headings:font-bold prose-headings:text-neutral-900
        prose-h2:text-xl prose-h2:mt-8 prose-h2:mb-4
        prose-h3:text-base prose-h3:mt-6 prose-h3:mb-2
        prose-p:text-neutral-700 prose-p:leading-7
        prose-li:text-neutral-700 prose-li:leading-7
        prose-blockquote:border-l-orange-300 prose-blockquote:text-neutral-500 prose-blockquote:text-sm
        prose-strong:text-neutral-900 prose-strong:font-semibold
        prose-code:text-orange-600 prose-code:bg-orange-50 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-sm prose-code:font-normal
        prose-hr:border-neutral-100
      ">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {content}
        </ReactMarkdown>
      </div>
    </article>
  );
}
