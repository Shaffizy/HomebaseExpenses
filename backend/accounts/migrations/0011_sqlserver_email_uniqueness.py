from django.db import migrations


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return
    schema_editor.execute("ALTER TABLE [accounts_connectedmailbox] ADD [email_normalized_mssql] AS LOWER([email]) PERSISTED")
    schema_editor.execute("CREATE UNIQUE INDEX [unique_connected_mailbox_per_org] ON [accounts_connectedmailbox] ([email_normalized_mssql], [organization_id])")


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return
    schema_editor.execute("DROP INDEX [unique_connected_mailbox_per_org] ON [accounts_connectedmailbox]")
    schema_editor.execute("ALTER TABLE [accounts_connectedmailbox] DROP COLUMN [email_normalized_mssql]")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0010_mailboxauthorization_connectedmailbox")]
    operations = [migrations.RunPython(create_index, drop_index)]
