import { fireEvent, render, screen } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';
import { useState } from 'react';

import { OtpInput } from '../otpInput';

function Form() {
  const [value, setValue] = useState('');
  return <OtpInput value={value} onValueChange={setValue} label="Verification code" />;
}

it('supports digits, leading zeros, backspace and replacement of a selected digit', async () => {
  const user = userEvent.setup();
  const { container } = render(<Form />);
  const input = screen.getByLabelText('Verification code');
  await user.type(input, 'ab001234');
  expect(input).toHaveValue('001234');
  await user.keyboard('{Backspace}');
  expect(input).toHaveValue('00123');
  await user.click(container.querySelectorAll('button')[1]);
  expect(input).toHaveFocus();
  await user.keyboard('9');
  expect(input).toHaveValue('09123');
});

it('accepts full-code paste and autofill, filtering non-digits and limiting to six digits', async () => {
  const user = userEvent.setup();
  render(<Form />);
  const input = screen.getByLabelText('Verification code');
  await user.click(input);
  await user.paste('01 2345 67');
  expect(input).toHaveValue('012345');
  fireEvent.change(input, { target: { value: '654321' } });
  expect(input).toHaveValue('654321');
  expect(input).toHaveAttribute('autocomplete', 'one-time-code');
});
