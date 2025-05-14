import { useEffect } from "react";

interface HeadProps {
  title: string;
  description: string;
}

function Head({ title, description }: HeadProps) {
  useEffect(() => {
    if (title) {
      document.title = title;
    }
    if (description) {
      document
        .querySelector('meta[name="description"]')
        ?.setAttribute("content", description);
    }
  }, [title, description]);
  return null;
}

export default Head;
