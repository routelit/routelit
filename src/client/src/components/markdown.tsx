import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";

interface MarkdownProps {
  body: string;
  allowUnsafeHtml?: boolean;
}

function Markdown({ body, allowUnsafeHtml = false }: MarkdownProps) {
  const rehypePlugins = useMemo(
    () => (allowUnsafeHtml ? [rehypeRaw] : []),
    [allowUnsafeHtml]
  );
  return <ReactMarkdown rehypePlugins={rehypePlugins}>{body}</ReactMarkdown>;
}

export default Markdown;
