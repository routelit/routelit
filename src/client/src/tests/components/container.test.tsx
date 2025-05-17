import { render, screen } from '@testing-library/react';
import Container from '../../components/container';

describe('Container Component', () => {
  it('renders children correctly', () => {
    render(
      <Container>
        <p>Test Content</p>
      </Container>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('passes attributes to the container div', () => {
    render(
      <Container className="custom-class" data-testid="container-test">
        <p>Test Content</p>
      </Container>
    );

    const container = screen.getByTestId('container-test');
    expect(container).toHaveClass('custom-class');
    expect(container.tagName).toBe('DIV');
  });
});
