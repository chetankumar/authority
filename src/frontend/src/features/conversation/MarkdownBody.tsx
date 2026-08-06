import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

const components: Components = {
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  ),
};

/** Safe CommonMark render for completed assistant / system chat messages.
 *  remark-breaks: models usually put single `\n` between lines; CommonMark
 *  would collapse those into spaces and mash paragraphs together. */
export function MarkdownBody({ children }: { children: string }) {
  return (
    <div className="chat-md font-prose text-ink">
      <ReactMarkdown remarkPlugins={[remarkBreaks]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  );
}
