
# -*- coding: utf-8 -*-
"""
Created on Fri Dec 27 15:58:13 2013

Esqueleto de agente usando los servicios web de Flask

/comm es la entrada para la recepcion de mensajes del agente
/Stop es la entrada que para el agente

Tiene una funcion AgentBehavior1 que se lanza como un thread concurrente

Asume que el agente de registro esta en el puerto 9000

@author: javier
"""

from __future__ import print_function

import argparse

from multiprocessing import Process, Queue
import socket

from amadeus import Client, ResponseError

from rdflib import Namespace, Graph, logger, RDF, XSD, Literal
from flask import Flask, request, jsonify

from PlanificadorViajes.AgentUtil.ACLMessages import register_agent, build_message, get_message_properties
from PlanificadorViajes.AgentUtil.FlaskServer import shutdown_server
from PlanificadorViajes.AgentUtil.Agent import Agent
from PlanificadorViajes.AgentUtil.OntologyNamespaces import ACL
from PlanificadorViajes.AgentUtil.OntologyNamespaces import Ontologia

__author__ = 'ecsdi'

parser = argparse.ArgumentParser()
parser.add_argument('--open', help="Define si el servidor est abierto al exterior o no", action='store_true',
                    default=False)
parser.add_argument('--port', type=int, help="Puerto de comunicacion del agente")
parser.add_argument('--dhost', default=socket.gethostname(), help="Host del agente de directorio")
parser.add_argument('--dport', type=int, help="Puerto de comunicacion del agente de directorio")
parser.add_argument('--host', default=socket.gethostname(), help="Host del agente")

args = parser.parse_args()

# Configuration stuff
if args.port is None:
    port = 9081
else:
    port = args.port

if args.open is None:
    hostname = '0.0.0.0'
else:
    hostname = args.host

if args.dport is None:
    dport = 9000
else:
    dport = args.dport

if args.dhost is None:
    dhostname = socket.gethostname()
else:
    dhostname = args.dhost


agn = Namespace("http://www.agentes.org/#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente

AgentePlanificador = Agent('Planificador',
                       agn.AgentePlanificador,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))

# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')

def get_count():
    global messages_cnt
    messages_cnt += 1
    return messages_cnt

def buscarVuelos(origen, destino, date, end, minP, maxP):
    amadeus = Client(
        client_id='s2h4iHhivYGEkIyyVuzNAUxL7SHxVpSl',
        client_secret='sUSz5eLygipHqv1C'
    )
    # date = dateToApi(request.args.get('date', None))
    # print(date)
    #return 'Quieres ir de '+origen+' a '+destino
    try:
        res = amadeus.shopping.flight_dates.get(
            origin=origen,
            destination=destino, departureDate=date
        )

        vuelos = res.result['data']

    except ResponseError as error:
        return error.response.result
    resultados = []
    for v in vuelos:
        pasta = float(v['price']['total'])
        if v['returnDate'].strip() == str(end).strip()\
                and pasta <= float(maxP) and pasta >= float(minP):
            resultados.append(v)
    if len(resultados) == 1:
        return resultados[0]
    elif len(resultados) == 0:
        return None
    else:
        precioMin = 0
        vueloMin = {}
        for v in resultados:
            if float(v['price']['total']) >= precioMin:
                precioMin =  float(v['price']['total'])
                vueloMin = v
        return vueloMin

def buscarHotel(ciudad, fecha, end):
    amadeus = Client(
        client_id='s2h4iHhivYGEkIyyVuzNAUxL7SHxVpSl',
        client_secret='sUSz5eLygipHqv1C'
    )
    # date = dateToApi(request.args.get('date', None))
    # print(date)
    # return 'Quieres ir de '+origen+' a '+destino
    try:
        res = amadeus.shopping.hotel_offers.get(cityCode=ciudad)

        hoteles = res.result['data']
    except ResponseError as error:
        return error.response.result
    precioMin = 0
    hotelMin = None
    for h in hoteles:
        try:
            if float(h['offers'][0]['price']['total']) >= precioMin:
                precioMin = float(h['offers'][0]['price']['total'])
                hotelMin = h
        except:
            pass
    return hotelMin


def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgentePlanificador, DirectoryAgent, AgentePlanificador.uri, get_count())
    return gr


@app.route("/comm")
def comunicacion():
    global dsgraph
    global mss_cnt
    gr =  None

    # Extraemos el mensaje que nos envian
    mensaje = request.args['content']
    gm = Graph()
    gm.parse(data=mensaje)

    msgdic = get_message_properties(gm)

    #Comprobacion del mensaje

    if msgdic is None:
        gr = build_message(Graph(), ACL['no_entendido'],sender=AgentePlanificador.uri, msgcnt=get_count())
    else:
        performative = msgdic['performative']

        if performative != ACL.request:
            gr = build_message(Graph(), ACL['no_entendido'], sender=AgentePlanificador.uri, msgcnt=get_count())

        else:

            content = msgdic['content']
            accion = gm.value(subject=content, predicate=RDF.type)
            if accion == Ontologia.EnviarFormularioPlanificar:
                
                beginning = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.beginning)
                tematica = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.tematica)
                precio_max = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.precio_max)
                ciudad_origen = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.ciudad_origen)
                ciudad_destino = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.ciudad_destino)
                end = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.end)
                precio_min = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.precio_min)
                correo = gm.value(subject=Ontologia.EnviarFormularioPlanificar, predicate=Ontologia.correo)

                viaje = buscarVuelos(ciudad_origen, ciudad_destino, beginning, end, precio_min, precio_max)
                hotel = buscarHotel(ciudad_destino, beginning, end)
                if viaje is not None and hotel is not None:
                    response = Graph()
                    precio = float(viaje['price']['total'])
                    precio += float(hotel['offers'][0]['price']['total'])
                    EnviarViajePlanificado = Ontologia.EnviarViajePlanificado
                    response.add((EnviarViajePlanificado, Ontologia.tematica, Literal(tematica)))
                    response.add((EnviarViajePlanificado, Ontologia.ciudad_destino, Literal(ciudad_destino)))
                    response.add((EnviarViajePlanificado, Ontologia.ciudad_origen, Literal(ciudad_origen)))
                    response.add((EnviarViajePlanificado, Ontologia.coste, Literal(precio)))
                    response.add((EnviarViajePlanificado, Ontologia.vuelo, Literal(viaje['links']['flightOffers'])))
                    response.add((EnviarViajePlanificado, Ontologia.correo, Literal(correo)))
                    response.add((EnviarViajePlanificado, Ontologia.nomHotel, Literal(hotel['hotel']['name'])))
                    response.add((EnviarViajePlanificado, Ontologia.linkHotel, Literal(hotel['self'])))

                #jsonVuelos = buscarVuelos(ciudad_origen, ciudad_destino)
                #print(jsonVuelos)

                    return response.serialize(format="xml"), 200
                else:
                    return '', 404

                # serialize = gr.serialize(format='xml')
                # return serialize, 200





@app.route("/Stop")
def stop():
    """
    Entrypoint que para el agente

    :return:
    """
    tidyup()
    shutdown_server()
    return "Parando Servidor"


def tidyup():
    """
    Acciones previas a parar el agente
    Guardar el grafo en un archivo
    """
    pass


def agentbehavior1():

    gr = register_message()

    pass



if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=())
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port, debug=True)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')

