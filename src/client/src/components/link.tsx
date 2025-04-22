interface LinkProps extends React.AnchorHTMLAttributes<HTMLAnchorElement> {
  is_external?: boolean;
  text?: string;
  replace?: boolean;
}

interface UINavigateEvent {
  id?: string;
  type: "navigate";
  href: string;
  replace?: boolean;
}

function Link({ text, children, id, href, replace, ...props }: LinkProps) {
  const handleClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
    if (props.is_external) {
      return;
    }
    e.preventDefault();
    e.stopPropagation();
    const event = new CustomEvent<UINavigateEvent>("routelit:event", {
      detail: {
        id: id!,
        type: "navigate",
        href: href!,
        replace: replace,
      },
    });
    document.dispatchEvent(event);
  };
  return (
    <a id={id} href={href} onClick={handleClick} {...props}>
      {text || children}
    </a>
  );
}

export default Link;
