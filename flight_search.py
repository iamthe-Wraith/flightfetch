import os
import json
import requests
import smtplib
from dotenv import load_dotenv

load_dotenv()

class FlightSearch:
    def __init__(self):
        self.BASE_URL = os.getenv('FLIGHT_BASE_URL')
        self.API_KEY = os.getenv('FLIGHT_API_KEY')
        self.API_SECRET = os.getenv('FLIGHT_API_SECRET')

        if (not self.API_KEY or not self.API_SECRET):
            print("Error: API key or secret not found")
            exit(1)

        self.ACCESS_TOKEN = self._get_new_token()
        
        self.flights = {}
        self.departure = {}
        self.destinations = []

        self._load_data()

    ###############################################
    #                PUBLIC METHODS               #
    ###############################################    

    def check_flights(self):
        self.ACCESS_TOKEN = self._get_new_token()

        headers = {
            'Authorization': f"Bearer {self.ACCESS_TOKEN}",
        }

        cheap_flights_found = {}

        for destination in self.destinations:
            try:
                params = {
                    'originLocationCode': self.departure['iata_code'],
                    'destinationLocationCode': destination['iata_code'],
                    'departureDate': '2025-02-01',
                    'adults': 2,
                    'currencyCode': 'USD',
                    'max': 10,
                }

                res = requests.get(
                    f"{self.BASE_URL}/v2/shopping/flight-offers",
                    params=params,
                    headers=headers
                )

                res.raise_for_status()
                data = res.json()['data']
                
                for flight in data:
                    if destination['city'] not in self.flights:
                        self.flights[destination['city']] = flight
                        cheap_flights_found[destination['city']] = flight
                    elif (flight['price']['total'] < self.flights[destination['city']]['price']['total']):
                            self.flights[destination['city']] = flight
                            cheap_flights_found[destination['city']] = flight
            except Exception as e:
                print(f"Error checking flights to {destination['city']}: {e}")

        self._save_data()
        self._send_flight_data(cheap_flights_found)
    
    ###############################################
    #               PRIVATE METHODS               #
    ###############################################

    def _get_iata_code(self, city, country_code):
        headers = {
            'Authorization': f"Bearer {self.ACCESS_TOKEN}",
        }

        try:
            params = {
                'countryCode': country_code,
                'keyword': city
            }

            res = requests.get(
                f"{self.BASE_URL}/v1/reference-data/locations/cities",
                headers=headers,
                params=params
            )

            res.raise_for_status()
            return res.json()['data'][0]['iataCode']
        except Exception as e:
            print(f"Error: {e}")
            exit(1)

    def _get_new_token(self):
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        data = {
            'grant_type': 'client_credentials',
            'client_id': self.API_KEY,
            'client_secret': self.API_SECRET
        }

        try:
            res = requests.post(
                f"{self.BASE_URL}/v1/security/oauth2/token",
                headers=headers,
                data=data
            )
            res.raise_for_status()
            return res.json()['access_token']
        except Exception as e:
            print(f"Failed to get access token: {e}")
            exit(1)

    def _load_data(self):
        try:
            with open('flight_data.json') as file:
                data = json.load(file)
                self.departure = data['departure']
                self.destinations = data['destinations']
                self.flights = data['flights']

                if (not self.departure):
                    raise Exception("Error: No departure found")
                
                if (not self.departure['iata_code']):
                    iata_code = self._get_iata_code(self.departure['city'], self.departure['country_code'])
                    self.departure['iata_code'] = iata_code

                if (not self.destinations):
                    raise Exception("Error: No destinations found")
                
                for destination in self.destinations:
                    if (not destination['iata_code']):
                        iata_code = self._get_iata_code(destination['city'], destination['country_code'])
                        destination['iata_code'] = iata_code
        except Exception as e:
            print(f"Error loading flight data: {e}")
            exit(1)

        self._save_data()
    
    def _save_data(self):
        try:
            with open('flight_data.json', "w") as file:
                json.dump(
                    {
                        'departure': self.departure,
                        'destinations': self.destinations,
                        'flights': self.flights
                    },
                    file,
                    indent=4
                )
        except Exception as e:
            print(f"Error updating flight data: {e}")
            exit(1)

    def _send_flight_data(self, cheap_flights_found):
        if len(cheap_flights_found) > 0:
            try:
                email_body = '';
                email_subject = f"Cheap Flight{'s' if len(cheap_flights_found) > 1 else ''} Found!"

                for city, flight in cheap_flights_found.items():
                    email_body += f"Found flight to {city} for ${flight['price']['total']} departing on {flight['itineraries'][0]['segments'][0]['departure']['at']}\n"
                    
                smtp_email = os.getenv('SMTP_EMAIL')
                smtp_token = os.getenv('SMTP_TOKEN')
                smtp_host = os.getenv('SMTP_HOST')
                smtp_port = os.getenv('SMTP_PORT')

                with smtplib.SMTP(smtp_host, smtp_port) as connection:
                    connection.starttls() # IMPORTANT: secures the connection with tls
                    connection.login(user=smtp_email, password=smtp_token)
                    connection.sendmail(
                        from_addr=smtp_email,
                        to_addrs=smtp_email,
                        msg=f"Subject:{email_subject}\n\n{email_body}"
                    )
            except Exception as e:
                print(f"Error sending flight data: {e}")

