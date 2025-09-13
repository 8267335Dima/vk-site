import React from 'react';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import Footer from './Footer';

const renderWithRouter = (ui) => {
  return render(ui, { wrapper: BrowserRouter });
};

describe('Footer Component', () => {
  it('should render the app name "Zenith"', () => {
    renderWithRouter(<Footer />);
    // ИЩЕМ ЗАГОЛОВОК УРОВНЯ 5 (h5), СОДЕРЖАЩИЙ ТЕКСТ "Zenith"
    const appNameElement = screen.getByRole('heading', {
      level: 5,
      name: /Zenith/i,
    });
    expect(appNameElement).toBeInTheDocument();
  });

  it('should render the current year in the copyright notice', () => {
    renderWithRouter(<Footer />);
    const currentYear = new Date().getFullYear();
    const yearElement = screen.getByText(
      `© ${currentYear} Zenith. Все права защищены.`
    );
    expect(yearElement).toBeInTheDocument();
  });
});
