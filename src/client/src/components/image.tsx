
interface ImageProps extends React.HTMLAttributes<HTMLImageElement> {
  src: string;
  alt: string;
}

function Image({ src, alt, ...props }: ImageProps) {
  return <img src={src} alt={alt} {...props} />;
}

export default Image;
