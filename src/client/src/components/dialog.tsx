import { useDispatcherWith } from "../lib";

function Dialog({
  id,
  children,
  closable = true,
  open = true,
}: {
  id: string;
  children: React.ReactNode;
  closable?: boolean;
  open?: boolean;
}) {
  const onClose = useDispatcherWith(id, "close");
  return (
    <dialog open={open}>
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
