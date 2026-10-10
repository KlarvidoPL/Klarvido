import { screen, waitFor } from '@testing-library/react';
import { userEvent } from '@testing-library/user-event';

import { render } from '../../../tests/utils/rendering';
import { ConfirmDialog, ConfirmDialogProps } from '../confirmDialog.component';

describe('ConfirmDialog: Component', () => {
  const title = 'Title';
  const defaultProps: ConfirmDialogProps = {
    title,
    onContinue: jest.fn(),
    onCancel: jest.fn(),
  };

  const Component = (props: Partial<ConfirmDialogProps>) => <ConfirmDialog {...defaultProps} {...props} />;

  it('should open dialog', async () => {
    const label = 'trigger';

    render(
      <Component>
        <button>{label}</button>
      </Component>
    );

    await userEvent.click(screen.getByText(label));

    expect(screen.getByText(title)).toBeInTheDocument();
  });

  describe('when open', () => {
    it('keeps confirmation open after a failed async action and closes after success', async () => {
      const onContinue = jest.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(true);
      render(
        <Component onContinue={onContinue} closeOnContinue={false} content={<p>Additional confirmation</p>}>
          <button>trigger</button>
        </Component>
      );
      await userEvent.click(screen.getByText('trigger'));
      await userEvent.click(screen.getByText('Continue'));
      expect(screen.getByText('Additional confirmation')).toBeInTheDocument();
      await userEvent.click(screen.getByText('Continue'));
      await waitFor(() => expect(screen.queryByText(title)).not.toBeInTheDocument());
    });

    it('disables Continue while an additional requirement is unmet', async () => {
      render(
        <Component continueDisabled>
          <button>trigger</button>
        </Component>
      );
      await userEvent.click(screen.getByText('trigger'));
      expect(screen.getByText('Continue')).toBeDisabled();
    });
    it('should continue', async () => {
      const trigger = 'trigger';
      const onContinue = jest.fn();
      render(
        <Component onContinue={onContinue}>
          <button>{trigger}</button>
        </Component>
      );

      await userEvent.click(screen.getByText(trigger));
      await userEvent.click(screen.getByText('Continue'));

      expect(onContinue).toBeCalled();
    });

    it('should cancel', async () => {
      const trigger = 'trigger';
      const onCancel = jest.fn();
      render(
        <Component onCancel={onCancel}>
          <button>{trigger}</button>
        </Component>
      );

      await userEvent.click(screen.getByText(trigger));
      await userEvent.click(screen.getByText('Cancel'));

      expect(onCancel).toBeCalled();
    });
  });
});
