import { render } from '@testing-library/react';
import Head from '../../components/head';

describe('Head Component', () => {
  it('sets document title when title prop is provided', () => {
    render(<Head title="Test Title" description="Test Description" />);

    expect(document.title).toBe('Test Title');
  });

  it('sets meta description when description prop is provided', () => {
    // Create a meta description element if it doesn't exist
    if (!document.querySelector('meta[name="description"]')) {
      const meta = document.createElement('meta');
      meta.setAttribute('name', 'description');
      document.head.appendChild(meta);
    }

    render(<Head title="Test Title" description="Test Description" />);

    const metaDescription = document.querySelector('meta[name="description"]');
    expect(metaDescription?.getAttribute('content')).toBe('Test Description');
  });

  it('updates title and description when props change', () => {
    // Create a meta description element if it doesn't exist
    if (!document.querySelector('meta[name="description"]')) {
      const meta = document.createElement('meta');
      meta.setAttribute('name', 'description');
      document.head.appendChild(meta);
    }

    const { rerender } = render(
      <Head title="Initial Title" description="Initial Description" />
    );

    expect(document.title).toBe('Initial Title');
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Initial Description');

    // Rerender with new props
    rerender(<Head title="Updated Title" description="Updated Description" />);

    expect(document.title).toBe('Updated Title');
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe('Updated Description');
  });
});
