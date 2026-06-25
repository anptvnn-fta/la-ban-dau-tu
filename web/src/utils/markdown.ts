import removeMd from 'remove-markdown';

/**
 * Chuyển đổi Markdown sang văn bản thuần túy
 * Sử dụng thư viện remove-markdown để xử lý Markdown đúng cách
 */
export function markdownToPlainText(markdown: string): string {
  if (!markdown) return '';

  const plainText = removeMd(markdown, {
    gfm: true,
    useImgAltText: true,
    stripListLeaders: true,
  });

  // Xóa thêm các dòng separator của bảng GFM (ví dụ |---|)
  // mà remove-markdown đôi khi để lại.
  return plainText
    .replace(/\n\|?[\s|:-]+\|?\s*(?=\n|$)/g, '\n')
    .trim();
}
