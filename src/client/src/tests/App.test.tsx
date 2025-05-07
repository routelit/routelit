import { render, screen } from '@testing-library/react';
import React from 'react';
import App from '../App';

// Mock the lib module
jest.mock('../lib', () => ({
  manager: {
    initialize: jest.fn(),
    terminate: jest.fn(),
  },
  componentStore: {},
}));

// Mock the context module
jest.mock('../core/context', () => {
  return {
    RouteLitContext: {
      Provider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    }
  };
});

// Mock ReactRenderer
jest.mock('../core/react-renderer', () => {
  return {
    __esModule: true,
    default: () => <div data-testid="react-renderer">Mocked React Renderer</div>,
  };
});

// Import the mocked manager after mocking
const { manager } = require('../lib');

describe('App', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders ReactRenderer component', () => {
    render(<App />);

    expect(screen.getByTestId('react-renderer')).toBeInTheDocument();
  });

  it('initializes manager on mount', () => {
    render(<App />);

    expect(manager.initialize).toHaveBeenCalledTimes(1);
  });

  it('terminates manager on unmount', () => {
    const { unmount } = render(<App />);

    unmount();

    expect(manager.terminate).toHaveBeenCalledTimes(1);
  });
});
