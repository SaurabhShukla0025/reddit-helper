import { settingText, type Policy } from './workflow.ts';

type Field = { fieldType?: number; stringValue?: string; selectionValue?: { values: string[] } };

// Read only installation values: legacy app-wide values must never override
// permission records for a particular community. Missing settings fail closed.
export function installationPolicy(fields: Record<string, Field> = {}): Policy {
  const text = (name: string) => {
    const field = fields[name];
    return settingText(field?.fieldType === 5 ? field.selectionValue?.values
      : field?.fieldType === 0 ? field.stringValue : undefined);
  };
  return { mode: text('operation-mode'), community: text('approved-community'), operator: 'saurabhimapro',
    permissionReference: text('permission-reference'), communityPermission: text('community-permission'),
    privacyContact: text('deletion-contact'), privacyUrl: text('privacy-url'), rulesReviewedOn: text('rules-reviewed-on') };
}
