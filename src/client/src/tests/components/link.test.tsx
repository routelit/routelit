import { render, screen, fireEvent } from '@testing-library/react';
import Link from '../../components/link';

describe('Link Component', () => {
  beforeEach(() => {
    // Clear any previous event listeners
    document.removeEventListener = jest.fn();
    document.addEventListener = jest.fn();
    document.dispatchEvent = jest.fn();
  });

  it('renders a link with text', () => {
    render(<Link href="/test" id="test-link">Test Link</Link>);

    const linkElement = screen.getByText('Test Link');
    expect(linkElement).toBeInTheDocument();
    expect(linkElement.getAttribute('href')).toBe('/test');
    expect(linkElement.getAttribute('id')).toBe('test-link');
  });

  it('renders a link with text prop', () => {
    render(<Link href="/test" text="Test Link Text" />);

    const linkElement = screen.getByText('Test Link Text');
    expect(linkElement).toBeInTheDocument();
  });

  it('dispatches a custom event on click for internal links', () => {
    const dispatchEventSpy = jest.spyOn(document, 'dispatchEvent');

    render(<Link href="/internal" id="internal-link">Internal Link</Link>);

    fireEvent.click(screen.getByText('Internal Link'));

    expect(dispatchEventSpy).toHaveBeenCalledTimes(1);

    // Verify the event details
    const customEvent = dispatchEventSpy.mock.calls[0][0] as CustomEvent;
    expect(customEvent.type).toBe('routelit:event');
    expect(customEvent.detail).toEqual({
      id: 'internal-link',
      type: 'navigate',
      href: '/internal',
      replace: undefined,
    });
  });

  it('does not dispatch an event for external links', () => {
    const dispatchEventSpy = jest.spyOn(document, 'dispatchEvent');

    render(
      <Link href="https://example.com" isExternal={true} id="external-link">
        External Link
      </Link>
    );

    fireEvent.click(screen.getByText('External Link'));

    expect(dispatchEventSpy).not.toHaveBeenCalled();
  });

  it('includes the replace property in the event when provided', () => {
    const dispatchEventSpy = jest.spyOn(document, 'dispatchEvent');

    render(
      <Link href="/replace" id="replace-link" replace={true}>
        Replace Link
      </Link>
    );

    fireEvent.click(screen.getByText('Replace Link'));

    expect(dispatchEventSpy).toHaveBeenCalledTimes(1);

    // Verify the event details
    const customEvent = dispatchEventSpy.mock.calls[0][0] as CustomEvent;
    expect(customEvent.detail.replace).toBe(true);
  });
});
