
function Container({ children, ...props }: { children: React.ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div {...props}>{children}</div>;
}

export default Container;
