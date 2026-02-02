# Migration Instructions for Member Import Feature

## Run these commands to apply database changes:

```bash
# Activate virtual environment (if not already active)
source ../venv/bin/activate

# Create migrations for new fields
python manage.py makemigrations members

# Apply migrations
python manage.py migrate members

# Restart the server to load new code
# Press Ctrl+C in the terminal running the server, then:
python manage.py runserver
```

## Expected Migration Changes:

The migration will add two new fields to the `members_member` table:
- `is_guest` (BooleanField, default=False, indexed)
- `import_batch_id` (CharField, nullable, indexed)

## Verification:

After migration, you can verify in Django shell:
```bash
python manage.py shell
```

```python
from members.models import Member
# Check if new fields exist
member = Member.objects.first()
print(member.is_guest)  # Should print False
print(member.import_batch_id)  # Should print None
```
