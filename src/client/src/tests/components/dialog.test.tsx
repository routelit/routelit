import { render, screen, fireEvent } from '@testing-library/react';
import Dialog from '../../components/dialog';
import { useDispatcherWith } from '../../lib';

// Mock the useDispatcherWith hook
jest.mock('../../lib', () => ({
  useDispatcherWith: jest.fn()
}));

describe('Dialog Component', () => {
  const mockOnClose = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
    (useDispatcherWith as jest.Mock).mockReturnValue(mockOnClose);
  });

  it('renders dialog with children', () => {
    render(
      <Dialog id="test-dialog">
        <p>Dialog Content</p>
      </Dialog>
    );

    expect(screen.getByText('Dialog Content')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('shows close button when closable is true (default)', () => {
    render(
      <Dialog id="test-dialog">
        <p>Dialog Content</p>
      </Dialog>
    );

    const closeButton = screen.getByRole('button', { name: '×' });
    expect(closeButton).toBeInTheDocument();

    // Clicking close button should call the onClose function
    fireEvent.click(closeButton);
    expect(mockOnClose).toHaveBeenCalledWith({});
  });

  it('does not show close button when closable is false', () => {
    render(
      <Dialog id="test-dialog" closable={false}>
        <p>Dialog Content</p>
      </Dialog>
    );

    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('properly passes open property to dialog element', () => {
    const { rerender } = render(
      <Dialog id="test-dialog" open={true}>
        <p>Dialog Content</p>
      </Dialog>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('open');

    // Rerender with open=false
    rerender(
      <Dialog id="test-dialog" open={false}>
        <p>Dialog Content</p>
      </Dialog>
    );

    expect(dialog).not.toHaveAttribute('open');
  });

  it('uses useDispatcherWith hook with correct parameters', () => {
    render(
      <Dialog id="test-dialog">
        <p>Dialog Content</p>
      </Dialog>
    );

    expect(useDispatcherWith).toHaveBeenCalledWith('test-dialog', 'close');
  });
});
