from django.db import migrations


def create_index(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return
    schema_editor.execute("ALTER TABLE [expenses_expensecategory] ADD [name_normalized_mssql] AS LOWER([name]) PERSISTED")
    schema_editor.execute("CREATE UNIQUE INDEX [unique_expense_category_per_org] ON [expenses_expensecategory] ([name_normalized_mssql], [organization_id])")


def drop_index(apps, schema_editor):
    if schema_editor.connection.vendor != "microsoft":
        return
    schema_editor.execute("DROP INDEX [unique_expense_category_per_org] ON [expenses_expensecategory]")
    schema_editor.execute("ALTER TABLE [expenses_expensecategory] DROP COLUMN [name_normalized_mssql]")


class Migration(migrations.Migration):
    dependencies = [("expenses", "0011_expense_approved_signature_data")]
    operations = [migrations.RunPython(create_index, drop_index)]
