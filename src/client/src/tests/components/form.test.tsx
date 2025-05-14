import { render, screen } from '@testing-library/react';
import Form, { useFormId } from '../../components/form';

// Create a test component that uses the useFormId hook
const TestComponent = () => {
  const formId = useFormId();
  return <div data-testid="form-id">{formId}</div>;
};

describe('Form Component', () => {
  it('renders a form with the specified id', () => {
    render(
      <Form id="test-form">
        <p>Form Content</p>
      </Form>
    );

    const form = screen.getByTestId('test-form');
    expect(form).toBeInTheDocument();
    expect(form).toHaveAttribute('id', 'test-form');
    expect(screen.getByText('Form Content')).toBeInTheDocument();
  });

  it('provides form id through context', () => {
    render(
      <Form id="context-test-form">
        <TestComponent />
      </Form>
    );

    expect(screen.getByTestId('form-id')).toHaveTextContent('context-test-form');
  });

  it('returns an empty string for useFormId when used outside a Form', () => {
    render(<TestComponent />);

    expect(screen.getByTestId('form-id')).toHaveTextContent('');
  });

  it('provides different form ids in different contexts', () => {
    // Test each form separately to avoid nesting forms
    const { unmount } = render(
      <Form id="outer-form">
        <TestComponent />
      </Form>
    );

    expect(screen.getByTestId('form-id')).toHaveTextContent('outer-form');

    // Unmount the first form
    unmount();

    // Render the second form
    render(
      <Form id="inner-form">
        <TestComponent />
      </Form>
    );

    expect(screen.getByTestId('form-id')).toHaveTextContent('inner-form');
  });
});
