import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { HelpTooltip } from './HelpTooltip'

describe('HelpTooltip', () => {
  it('shows the same accessible explanation on hover and keyboard focus', () => {
    render(<HelpTooltip text="Wyjaśnienie pola"/>)
    const trigger = screen.getByRole('button', { name: 'Podpowiedź' })
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.mouseEnter(trigger.parentElement!)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Wyjaśnienie pola')
    fireEvent.mouseLeave(trigger.parentElement!)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.focus(trigger)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Wyjaśnienie pola')
    fireEvent.blur(trigger)
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    fireEvent.click(trigger)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Wyjaśnienie pola')
  })
})
