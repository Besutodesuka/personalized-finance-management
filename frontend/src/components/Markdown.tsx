'use client'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Components } from 'react-markdown'

// Tailwind-styled renderers tuned for a chat bubble (compact spacing, no prose
// plugin needed). Block margins collapse at the edges so the bubble padding
// stays tight.
const components: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  ul: ({ children }) => <ul className="list-disc pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-5 mb-2 last:mb-0 space-y-0.5">{children}</ol>,
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noreferrer noopener"
       className="text-indigo-600 underline hover:text-indigo-800">{children}</a>
  ),
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  h1: ({ children }) => <h1 className="text-base font-bold mb-1.5 mt-2 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-bold mb-1.5 mt-2 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mb-1 mt-2 first:mt-0">{children}</h3>,
  blockquote: ({ children }) => (
    <blockquote className="border-l-2 border-gray-300 pl-3 italic text-gray-600 my-2">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-gray-200" />,
  pre: ({ children }) => (
    <pre className="bg-gray-800 text-gray-100 rounded-lg p-3 overflow-x-auto text-xs my-2">{children}</pre>
  ),
  code: ({ className, children }) => {
    // Block code is fenced (has a language- class) or spans multiple lines;
    // everything else is treated as inline.
    const isBlock = /language-/.test(className || '') || String(children).includes('\n')
    return isBlock ? (
      <code className={className}>{children}</code>
    ) : (
      <code className="bg-black/10 rounded px-1 py-0.5 text-[0.85em] font-mono">{children}</code>
    )
  },
  table: ({ children }) => (
    <div className="overflow-x-auto my-2">
      <table className="min-w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="border-b border-gray-300">{children}</thead>,
  th: ({ children }) => <th className="text-left font-semibold px-2 py-1">{children}</th>,
  td: ({ children }) => <td className="px-2 py-1 border-t border-gray-200">{children}</td>,
}

export default function Markdown({ children }: { children: string }) {
  return (
    <div className="break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
