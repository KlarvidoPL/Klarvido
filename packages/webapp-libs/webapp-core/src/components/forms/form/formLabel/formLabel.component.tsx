import * as LabelPrimitive from '@radix-ui/react-label';
import React from 'react';

import { useFormField } from '../';
import { cn } from '../../../../lib/utils';

const FormLabel = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => {
  const { error, formItemId } = useFormField();

  return (
    <label
      ref={ref}
      className={cn(
        'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
        // dark:text-red-400 mirrors the Alert component's destructive variant -
        // --destructive itself is tuned dark (for text on a filled button), so it
        // reads as low contrast on a near-black background.
        error && 'text-destructive dark:text-red-400',
        className
      )}
      htmlFor={formItemId}
      {...props}
    />
  );
});
FormLabel.displayName = 'FormLabel';

export { FormLabel };
