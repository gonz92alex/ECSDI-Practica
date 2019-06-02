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
import datetime
import sys

from multiprocessing import Process, Queue
import socket


from rdflib import Namespace, Graph, logger, RDF, XSD, Literal
from flask import Flask, request

from PracticaTienda.utils.ACLMessages import get_message_properties, build_message, register_agent, send_message, \
    get_bag_agent_info
from PracticaTienda.utils.FlaskServer import shutdown_server
from PracticaTienda.utils.Agent import Agent
from PracticaTienda.utils.OntoNamespaces import ACL
from PracticaTienda.utils.OntologyNamespaces import ECSDI

__author__ = 'Amazon V2'

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
    port = 9011
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


agn = Namespace("http://www.agentes.org#")

# Contador de mensajes
messages_cnt = 0

# Datos del Agente

AgenteNegociador = Agent('AgenteNegociador',
                       agn.AgenteNegociador,
                       'http://%s:%d/comm' % (hostname, port),
                       'http://%s:%d/Stop' % (hostname, port))

# Directory agent address
DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:%d/Register' % (dhostname, dport),
                       'http://%s:%d/Stop' % (dhostname, dport))


DirectoryAgent = Agent('DirectoryAgent',
                       agn.Directory,
                       'http://%s:9000/Register' % hostname,
                       'http://%s:9000/Stop' % hostname)


# Global triplestore graph
dsgraph = Graph()

cola1 = Queue()

# Flask stuff
app = Flask(__name__, template_folder='../templates')

def get_count():
    global messages_cnt
    messages_cnt += 1
    return messages_cnt

def register_message():
    """
    Envia un mensaje de registro al servicio de registro
    usando una performativa Request y una accion Register del
    servicio de directorio
    :param gmess:
    :return:
    """

    logger.info('Nos registramos')

    gr = register_agent(AgenteNegociador, DirectoryAgent, AgenteNegociador.uri, get_count())
    return gr


@app.route("/comm")
def comunicacion():
    """
       Communication Entrypoint
       """

    logger.info('Peticion de informacion recibida')
    global dsGraph

    message = request.args['content']
    gm = Graph()
    gm.parse(data=message)

    msgdic = get_message_properties(gm)

    if msgdic is None:
        # Si no es, respondemos que no hemos entendido el mensaje
        gr = build_message(Graph(), ACL['not-understood'], sender=AgenteNegociador.uri, msgcnt=get_count())
    else:
        # Obtenemos la performativa
        if msgdic['performative'] != ACL.request:
            # Si no es un request, respondemos que no hemos entendido el mensaje
            gr = build_message(Graph(),
                               ACL['not-understood'],
                               sender=DirectoryAgent.uri,
                               msgcnt=get_count())
        else:
            # Extraemos el objeto del contenido que ha de ser una accion de la ontologia
            # de registro
            content = msgdic['content']
            # Averiguamos el tipo de la accion
            accion = gm.value(subject=content, predicate=RDF.type)

            # Accion de busqueda
            if accion == ECSDI.Peticion_Transporte:
                logger.info("Negociamos con los transportistas")
                respondePeticion(gm, content)
                gr = Graph()

            # No habia ninguna accion en el mensaje
            else:
                gr = build_message(Graph(),
                                   ACL['not-understood'],
                                   sender=DirectoryAgent.uri,
                                   msgcnt=get_count())

    logger.info('Respondemos a la peticion')

    return gr.serialize(format='xml')





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


def requestOffer(agent, peso, fecha, destino):
    gr = Graph()
    subject = ECSDI['peticion-oferta']
    gr.add((subject, RDF.type, ECSDI.Pedir_oferta_transporte))
    gr.add((subject, ECSDI.Destino, Literal(destino)))
    gr.add((subject, ECSDI.Plazo_maximo_entrega, Literal(fecha)))
    gr.add((subject, ECSDI.Peso_envio, Literal(peso)))
    resp = send_message(build_message(gr, ACL['call-for-proposal'], content=subject, receiver=agent.uri,
                                      sender=AgenteNegociador.uri), agent.address)
    msg = get_message_properties(resp)
    if 'performative' not in msg or msg['performative'] == ACL.refuse:
        logger.warn('Nos ha rechazado un agente')
        return None
    elif msg['performative'] == ACL.propose:
        precio = resp.value(msg['content'], ECSDI.Precio_envio)
        return Offer(address=agent.address, price=precio.toPython())
    logger.error('No se entiende')
    return None


def acceptOffer(offer):
    resp = send_message(build_message(Graph(), ACL['accept-proposal'], sender=AgenteNegociador.uri),
                        offer.address)
    msg = get_message_properties(resp)
    return msg['performative'] == ACL.inform


def counter_offer(offer):
    logger.info('Asking counter-offer to ' + offer.address)
    gr = Graph()
    subject = ECSDI['contra-oferta']
    gr.add((subject, RDF.type, ECSDI.Contraoferta))
    new_price = offer.price - 2
    gr.add((subject, ECSDI.Precio_envio, Literal(new_price)))
    resp = send_message(build_message(gr, ACL['counter-proposal'], content=subject, sender=AgenteNegociador.uri),
                        offer.address)
    msg = get_message_properties(resp)
    if 'performative' not in msg or msg['performative'] == ACL.refuse:
        logger.warn('An agent rejected us :(')
        return None
    elif msg['performative'] == ACL.agree:
        return Offer(address=offer.address, price=new_price)
    else:
        logger.error('I can\'t understand:(')
        return None


def rejectOffer(offer):
    resp = send_message(build_message(Graph(), ACL['reject-proposal'], sender=AgenteNegociador.uri),
                        offer.address)
    msg = get_message_properties(resp)


def requestTransports(peso, fecha, destino):
    agents = get_bag_agent_info(agn.ExternalTransportAgent, ExternalTransportDirectory, AgenteNegociador, 192310291)
    offers = []
    for agent in agents:
        offer = requestOffer(agent, peso, fecha, destino)
        logger.info('Offer received of ' + str(offer.price))
        if offer:
            offers += [offer]
    offers2 = []
    for i, offer in enumerate(offers):
        offer2 = counter_offer(offer)
        if offer2:
            logger.info('Counter offer accepted at ' + str(offer2.price))
            offers2 += [offer2]
        else:
            logger.info('Counter offer rejected by ' + str(offer.address))
            offers2 += [offer]
    best_offer = min(offers2, key=lambda a: a.price)
    logger.info('La mejor oferta es la de ' + str(best_offer.price) + '€')
    end = False
    for offer in offers2:
        if offer == best_offer:
            end = acceptOffer(best_offer)
        else:
            rejectOffer(offer)
    if end:
        logger.info('La negociacion se ha realizado con exito')
        return best_offer
    else:
        return None


class Offer(object):
    def __init__(self, price, address):
        self.price = price
        self.address = address


def respondePeticion(gm, content):
    peso = gm.value(subject=content, predicate=ECSDI.Peso_envio)
    fecha = gm.value(subject=content, predicate=ECSDI.Fecha)

    offer = requestTransports(peso, datetime.datetime.fromtimestamp(float(fecha) / 1000.0), 'Barcelona')

def agentbehavior1():

    gr = register_message()

    pass

if __name__ == '__main__':
    # Ponemos en marcha los behaviors
    ab1 = Process(target=agentbehavior1, args=())
    ab1.start()

    # Ponemos en marcha el servidor
    app.run(host=hostname, port=port)

    # Esperamos a que acaben los behaviors
    ab1.join()
    print('The End')
