import * as React from 'react';

import { useFormField } from '../';
import { cn } from '../../../../lib/utils';

const FormMessage = React.forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, children, ...props }, ref) => {
    const { error, formMessageId } = useFormField();
    const body = error ? String(error?.message) : children;

    if (!body) {
      return null;
    }

    return (
      <p
        ref={ref}
        id={formMessageId}
        // dark:text-red-400 mirrors the Alert component's destructive variant - see
        // that component for why --destructive alone reads as low contrast here.
        className={cn('text-destructive dark:text-red-400 text-sm font-medium', className)}
        {...props}
      >
        {body}
      </p>
    );
  }
);
FormMessage.displayName = 'FormMessage';

export { FormMessage };
