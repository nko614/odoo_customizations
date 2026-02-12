# Google Maps Helper - CRM Lead Closest Distributors

This Odoo module extends CRM leads to automatically find the 3 closest distributors based on partner addresses using Google Maps Distance Matrix API.

## Features

- **Automatic Distance Calculation**: Uses Google Maps API to calculate distances between leads and distributors
- **Closest Distributor Finding**: Automatically finds the 3 closest distributors for each CRM lead
- **Configurable API Key**: Secure configuration through Odoo settings
- **User-Friendly Interface**: Simple button click to find closest distributors
- **Error Handling**: Comprehensive error messages and logging
- **Address Validation**: Validates partner addresses before API calls

## Installation

1. Install the module in your Odoo instance
2. Configure your Google Maps API key (see Configuration section)
3. Ensure distributors have the "Distributor" category tag
4. Add complete addresses to both leads' partners and distributors

## Configuration

### Google Maps API Key Setup

1. Go to **Settings > General Settings**
2. Find the "Google Maps API Key" field
3. Enter your Google Maps API key
4. Save the settings

### Getting a Google Maps API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the "Distance Matrix API"
4. Create credentials (API Key)
5. Copy the API key to Odoo settings

**Note**: The API key should have Distance Matrix API enabled and appropriate restrictions set.

## Usage

### Finding Closest Distributors

1. Open a CRM Lead
2. Ensure the lead has a partner assigned with a complete address
3. Click the "Find Closest Distributors" button
4. The system will automatically find and populate the 3 closest distributors

### Distributor Setup

1. Create or edit partners that are distributors
2. Add the "Distributor" category tag to these partners
3. Ensure complete address information (street, city, state, zip, country)

### Server Action

The module also provides a server action that can be used in automated workflows:
- **Name**: "Find Closest Distributors"
- **Model**: CRM Lead
- **Available in**: CRM Lead list view actions

## Technical Details

### Dependencies
- `crm`: CRM module for lead management
- `contacts`: Contact management
- `base`: Core Odoo functionality

### Models
- `crm.lead`: Extended with closest distributors field
- `google.maps.helper`: Abstract model for Google Maps API integration
- `res.config.settings`: Configuration for API key

### API Usage
- Uses Google Maps Distance Matrix API
- Calculates driving distances between addresses
- Returns top 3 closest distributors by distance
- Handles API errors gracefully

## Troubleshooting

### Common Issues

1. **"API key not configured" error**
   - Solution: Set the Google Maps API key in Settings > General Settings

2. **"No distributors found" error**
   - Solution: Ensure distributors have the "Distributor" category tag and complete addresses

3. **"Partner has no address" error**
   - Solution: Add complete address information to the lead's partner

4. **API request failures**
   - Check your API key is valid and has Distance Matrix API enabled
   - Verify address formats are correct
   - Check network connectivity

### Logging

The module provides detailed logging for troubleshooting:
- Check Odoo logs for detailed error messages
- API responses and errors are logged
- Address validation results are logged

## Security Notes

- API keys are stored securely in system parameters
- No hardcoded credentials in the code
- API requests use HTTPS
- Timeout protection prevents hanging requests

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review Odoo logs for error details
3. Verify API key and address configurations
4. Contact your system administrator if needed 