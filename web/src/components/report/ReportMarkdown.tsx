import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** Hiển thị nội dung Markdown của báo cáo với style gọn gàng. */
export function ReportMarkdown({ content }: { content: string }) {
  return (
    <div
      className={[
        'max-w-none text-sm leading-7 text-foreground/90',
        '[&_h1]:mt-4 [&_h1]:mb-2 [&_h1]:font-heading [&_h1]:text-lg [&_h1]:font-bold [&_h1]:text-foreground',
        '[&_h2]:mt-4 [&_h2]:mb-2 [&_h2]:font-heading [&_h2]:text-base [&_h2]:font-bold [&_h2]:text-foreground',
        '[&_h3]:mt-3 [&_h3]:mb-1.5 [&_h3]:font-heading [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:text-foreground',
        '[&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5',
        '[&_li]:my-0.5 [&_strong]:font-semibold [&_strong]:text-foreground',
        '[&_blockquote]:border-l-2 [&_blockquote]:border-primary [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground',
        '[&_table]:my-3 [&_table]:w-full [&_table]:text-xs [&_th]:border-b [&_th]:border-border [&_th]:px-2 [&_th]:py-1.5 [&_th]:text-left',
        '[&_td]:border-b [&_td]:border-border/60 [&_td]:px-2 [&_td]:py-1.5',
        '[&_code]:rounded [&_code]:bg-secondary [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs',
        '[&_a]:text-primary [&_a]:underline',
      ].join(' ')}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  )
}
