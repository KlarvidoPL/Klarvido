import { FormattedMessage } from 'react-intl';

export type SummaryRow = {
  label: string;
  value: string | undefined;
  editStep: number;
};

// Read-only review of the whole profile. Each row has its own Edit action that returns to the step that owns it.
export const SummaryStep = ({ rows, onEdit }: { rows: SummaryRow[]; onEdit: (step: number) => void }) => (
  <>
    <div>
      <h2 className="text-base font-semibold">
        <FormattedMessage defaultMessage="Your business profile" id="Onboarding / Summary title" />
      </h2>
      <p className="text-xs text-muted-foreground">
        <FormattedMessage
          defaultMessage="This is a starting point for future analysis."
          id="Onboarding / Summary hint"
        />
      </p>
    </div>
    <dl className="divide-y rounded-lg border">
      {rows.map(({ label, value, editStep }) => (
        <div key={label} className="grid grid-cols-[7rem_1fr_auto] lg:grid-cols-[11rem_1fr_auto] items-start gap-4 px-4 py-3 text-sm">
          <dt className="text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
          <button
            type="button"
            className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            onClick={() => onEdit(editStep)}
          >
            <FormattedMessage defaultMessage="Edit" id="Onboarding / Edit" />
          </button>
        </div>
      ))}
    </dl>
  </>
);
