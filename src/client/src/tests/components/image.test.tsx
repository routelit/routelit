import { render, screen } from '@testing-library/react';
import Image from '../../components/image';

describe('Image Component', () => {
  it('renders an image with src and alt attributes', () => {
    render(<Image src="/test-image.jpg" alt="Test image description" />);

    const image = screen.getByAltText('Test image description');
    expect(image).toBeInTheDocument();
    expect(image.tagName).toBe('IMG');
    expect(image).toHaveAttribute('src', '/test-image.jpg');
  });

  it('passes additional props to the img element', () => {
    render(
      <Image
        src="/test-image.jpg"
        alt="Test image"
        className="custom-class"
        data-testid="test-image"
        style={{ width: 300, height: 200 }}
      />
    );

    const image = screen.getByTestId('test-image');
    expect(image).toHaveClass('custom-class');
    expect(image.style.width).toBe('300px');
    expect(image.style.height).toBe('200px');
  });
});
