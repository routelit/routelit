import { useDispatcherWith } from "../lib";

function Dialog({
  id,
  children,
  closable = true,
  open = true,
  ...props
}: {
  id: string;
  children: React.ReactNode;
  closable?: boolean;
  open?: boolean;
} & React.HTMLAttributes<HTMLDialogElement>) {
  const onClose = useDispatcherWith(id, "close");
  return (
    <dialog open={open} {...props}>
      {closable && (
        <button className="close-button" onClick={() => onClose({})}>
          &times;
        </button>
      )}
      {children}
    </dialog>
  );
}

export default Dialog;
