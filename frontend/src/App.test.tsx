/**
 * Tests for the root App component with routing.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

describe('App', () => {
  it('renders navigation header', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    expect(screen.getByText('CatSyphon')).toBeInTheDocument();
  });

  it('renders Conversations navigation link', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    const conversationsLink = screen.getByText('Conversations');
    expect(conversationsLink).toBeInTheDocument();
    expect(conversationsLink.closest('a')).toHaveAttribute('href', '/conversations');
  });

  it('renders Ingestion navigation link', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    const ingestionLink = screen.getByText('Ingestion');
    expect(ingestionLink).toBeInTheDocument();
    expect(ingestionLink.closest('a')).toHaveAttribute('href', '/ingestion');
  });

  it('renders CatSyphon brand link to home', () => {
    render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    const brandLink = screen.getByText('CatSyphon');
    expect(brandLink.closest('a')).toHaveAttribute('href', '/');
  });

  it('has proper semantic HTML structure', () => {
    const { container } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    expect(container.querySelector('nav')).toBeInTheDocument();
    expect(container.querySelector('main')).toBeInTheDocument();
  });

  it('applies correct CSS classes for layout', () => {
    const { container } = render(
      <MemoryRouter>
        <App />
      </MemoryRouter>
    );

    const root = container.firstChild as HTMLElement;
    expect(root).toHaveClass('min-h-screen', 'bg-background');
  });
});
